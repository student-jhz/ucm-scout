import argparse
import json
import mmap
import secrets
import time
import os

import numpy as np

from ucm.store.factory_v1 import UcmConnectorFactoryV1


def parse_args():
    p = argparse.ArgumentParser(description="UCM Store Bandwidth Benchmark")
    p.add_argument("--shard-size", type=int, required=True)
    p.add_argument("--shard-number", type=int, required=True)
    p.add_argument("--block-number", type=int, required=True)
    p.add_argument("--storage-backend", type=str, required=True)
    p.add_argument("--dump-epochs", type=int, default=8)
    p.add_argument("--load-epochs", type=int, default=8)
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


def create_store(shard_size, shard_number, storage_backend):
    config = {
        "store_pipeline": "Posix",
        "posix_io_engine": "aio",
        "storage_backends": [storage_backend],
        "tensor_size": shard_size,
        "shard_size": shard_size,
        "block_size": shard_size * shard_number,
        "device_id": -1,
    }
    return UcmConnectorFactoryV1.create_connector(
        "UcmPipelineStore", config, "ucm.store.pipeline.connector"
    )


def run_epochs(store, block_ids, block_ptr, shard_size, shard_number,
               block_number, epochs, mode):
    total_size = shard_size * shard_number * block_number
    costs = []

    for epoch in range(epochs):
        epoch_costs = []
        for i in range(shard_number):
            idxes = [i for _ in range(block_number)]
            ptrs = [[ptr + i * shard_size] for ptr in block_ptr]
            tp = time.perf_counter()
            if mode == "dump":
                task = store.dump_data(block_ids, idxes, ptrs)
            else:
                task = store.load_data(block_ids, idxes, ptrs)
            store.wait(task)
            epoch_costs.append(time.perf_counter() - tp)
        total_cost = sum(epoch_costs)
        bw = total_size / max(total_cost, 1e-9) / 1e9
        costs.append({
            "epoch": epoch,
            "avg_cost_ms": np.average(epoch_costs) * 1e3,
            "total_cost_ms": total_cost * 1e3,
            "bw_gbs": bw,
        })
        print(f"[{mode}] epoch={epoch:03} shards={shard_number} blocks={block_number} "
              f"total={total_size}B bw={bw:.3f}GB/s")

    return costs


def main():
    args = parse_args()

    os.makedirs(os.path.dirname(args.storage_backend) or ".", exist_ok=True)
    store = create_store(args.shard_size, args.shard_number, args.storage_backend)

    block_ids = [secrets.token_bytes(16) for _ in range(args.block_number)]
    block_data = [make_array(args.shard_size * args.shard_number)
                  for _ in range(args.block_number)]
    block_ptr = [block.ctypes.data for block in block_data]

    dump_costs = run_epochs(store, block_ids, block_ptr,
                            args.shard_size, args.shard_number, args.block_number,
                            args.dump_epochs, "dump")

    load_costs = run_epochs(store, block_ids, block_ptr,
                            args.shard_size, args.shard_number, args.block_number,
                            args.load_epochs, "load")

    dump_bw = [c["bw_gbs"] for c in dump_costs]
    load_bw = [c["bw_gbs"] for c in load_costs]

    result = {
        "shard_size": args.shard_size,
        "shard_number": args.shard_number,
        "block_number": args.block_number,
        "total_size_bytes": args.shard_size * args.shard_number * args.block_number,
        "dump_epochs": args.dump_epochs,
        "load_epochs": args.load_epochs,
        "dump_avg_bw_gbs": float(np.mean(dump_bw)),
        "dump_p99_bw_gbs": float(np.percentile(dump_bw, 99)),
        "load_avg_bw_gbs": float(np.mean(load_bw)),
        "load_p99_bw_gbs": float(np.percentile(load_bw, 99)),
        "dump_costs": dump_costs,
        "load_costs": load_costs,
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
