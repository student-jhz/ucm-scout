import argparse
import json
import mmap
import multiprocessing
import secrets
import time
import os
import glob

import numpy as np

from ucm.store.factory_v1 import UcmConnectorFactoryV1


def parse_args():
    p = argparse.ArgumentParser(description="UCM Store Bandwidth Benchmark")
    p.add_argument("--worker-number", type=int, default=1)
    p.add_argument("--shard-size", type=int, required=True)
    p.add_argument("--shard-number", type=int, required=True)
    p.add_argument("--block-number", type=int, default=64)
    p.add_argument("--storage-backend", type=str, required=True)
    p.add_argument("--dump-epochs", type=int, default=32)
    p.add_argument("--load-epochs", type=int, default=32)
    p.add_argument("--output", type=str, default="/tmp/ucm_bench_result.json")
    return p.parse_args()


def make_array(size, alignment=262144, dtype=np.uint8):
    itemsize = np.dtype(dtype).itemsize
    total_bytes = size * itemsize
    mm = mmap.mmap(-1, total_bytes + alignment)
    raw_array = np.frombuffer(mm, dtype=np.uint8, count=total_bytes + alignment)
    raw_ptr = raw_array.__array_interface__["data"][0]
    aligned_addr = (raw_ptr + alignment - 1) & ~(alignment - 1)
    offset = aligned_addr - raw_ptr
    return raw_array[offset:offset + total_bytes].view(dtype=dtype)


def create_store(shard_size, shard_number, storage_backend, device_id=-1):
    config = {
        "store_pipeline": "Posix",
        "posix_io_engine": "aio",
        "storage_backends": [storage_backend],
        "tensor_size": shard_size,
        "shard_size": shard_size,
        "block_size": shard_size * shard_number,
        "device_id": device_id,
    }
    return UcmConnectorFactoryV1.create_connector(
        "UcmPipelineStore", config, "ucm.store.pipeline.connector"
    )


def run_dump(epoch, device_id, store, block_ids, block_ptr, shard_size, shard_number, block_number):
    total_size = shard_size * shard_number * block_number
    costs = []
    for i in range(shard_number):
        idxes = [i for _ in range(block_number)]
        ptrs = [[ptr + i * shard_size] for ptr in block_ptr]
        tp = time.perf_counter()
        task = store.dump_data(block_ids, idxes, ptrs)
        store.wait(task)
        costs.append(time.perf_counter() - tp)
    total_cost = np.sum(costs)
    print(
        f"epoch={epoch:03}, worker={device_id:02}, "
        f"dump=[{shard_size} x {block_number} x {shard_number}], "
        f"avg_cost={np.average(costs) * 1e3:.3f}ms, "
        f"p99_cost={np.percentile(costs, 99) * 1e3:.3f}ms, "
        f"total_cost={total_cost * 1e3:.3f}ms, "
        f"bw={total_size / total_cost / 1e9:.3f}GB/s."
    )
    return {
        "epoch": epoch,
        "worker": device_id,
        "avg_cost_ms": np.average(costs) * 1e3,
        "p99_cost_ms": np.percentile(costs, 99) * 1e3,
        "total_cost_ms": total_cost * 1e3,
        "bw_gbs": total_size / total_cost / 1e9,
    }


def run_load(epoch, device_id, store, block_ids, block_ptr, shard_size, shard_number, block_number):
    total_size = shard_size * shard_number * block_number
    costs = []
    for i in range(shard_number):
        idxes = [i for _ in range(block_number)]
        ptrs = [[ptr + i * shard_size] for ptr in block_ptr]
        tp = time.perf_counter()
        task = store.load_data(block_ids, idxes, ptrs)
        store.wait(task)
        costs.append(time.perf_counter() - tp)
    total_cost = np.sum(costs)
    print(
        f"epoch={epoch:03}, worker={device_id:02}, "
        f"load=[{shard_size} x {block_number} x {shard_number}], "
        f"avg_cost={np.average(costs) * 1e3:.3f}ms, "
        f"p99_cost={np.percentile(costs, 99) * 1e3:.3f}ms, "
        f"total_cost={total_cost * 1e3:.3f}ms, "
        f"bw={total_size / total_cost / 1e9:.3f}GB/s."
    )
    return {
        "epoch": epoch,
        "worker": device_id,
        "avg_cost_ms": np.average(costs) * 1e3,
        "p99_cost_ms": np.percentile(costs, 99) * 1e3,
        "total_cost_ms": total_cost * 1e3,
        "bw_gbs": total_size / total_cost / 1e9,
    }


def worker_loop(device_id, barrier, shard_size, shard_number,
                block_number, storage_backend, dump_epochs, load_epochs,
                output_prefix):
    store = create_store(shard_size, shard_number, storage_backend, device_id)
    block_ids = [secrets.token_bytes(16) for _ in range(block_number)]
    block_data = [make_array(shard_size * shard_number) for _ in range(block_number)]
    block_ptr = [block.ctypes.data for block in block_data]

    worker_results = {"dump": [], "load": []}

    barrier.wait()
    for epoch in range(dump_epochs):
        r = run_dump(epoch, device_id, store, block_ids, block_ptr,
                     shard_size, shard_number, block_number)
        worker_results["dump"].append(r)
        barrier.wait()

    for epoch in range(load_epochs):
        r = run_load(epoch, device_id, store, block_ids, block_ptr,
                     shard_size, shard_number, block_number)
        worker_results["load"].append(r)
        barrier.wait()

    worker_file = f"{output_prefix}.worker{device_id}"
    with open(worker_file, "w") as f:
        json.dump(worker_results, f)
    print(f"[worker {device_id}] results saved to {worker_file}")


def main():
    args = parse_args()

    os.makedirs(os.path.dirname(args.storage_backend) or ".", exist_ok=True)

    barrier = multiprocessing.Barrier(args.worker_number)
    workers = []

    output_prefix = args.output.replace(".json", "")

    for i in range(args.worker_number):
        p = multiprocessing.Process(
            target=worker_loop,
            args=(i, barrier, args.shard_size, args.shard_number,
                  args.block_number, args.storage_backend,
                  args.dump_epochs, args.load_epochs,
                  output_prefix),
        )
        workers.append(p)
        p.start()

    for w in workers:
        w.join()

    all_dump = []
    all_load = []

    for i in range(args.worker_number):
        worker_file = f"{output_prefix}.worker{i}"
        try:
            with open(worker_file, "r") as f:
                data = json.load(f)
            if data.get("dump"):
                all_dump.extend(data["dump"])
            if data.get("load"):
                all_load.extend(data["load"])
        except Exception as e:
            print(f"[main] WARN: failed to read {worker_file}: {e}")
        finally:
            try:
                os.remove(worker_file)
            except OSError:
                pass

    dump_bw = [c["bw_gbs"] for c in all_dump] if all_dump else [0.0]
    load_bw = [c["bw_gbs"] for c in all_load] if all_load else [0.0]

    total_size = args.shard_size * args.shard_number * args.block_number

    result = {
        "worker_number": args.worker_number,
        "shard_size": args.shard_size,
        "shard_number": args.shard_number,
        "block_number": args.block_number,
        "total_size_bytes": total_size * args.worker_number,
        "dump_epochs": args.dump_epochs,
        "load_epochs": args.load_epochs,
        "dump_avg_bw_gbs": float(np.mean(dump_bw)),
        "dump_p99_bw_gbs": float(np.percentile(dump_bw, 99)),
        "load_avg_bw_gbs": float(np.mean(load_bw)),
        "load_p99_bw_gbs": float(np.percentile(load_bw, 99)),
        "dump_costs": all_dump,
        "load_costs": all_load,
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
