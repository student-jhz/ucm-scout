import os
import re
import json
import time
from datetime import datetime
from config import REMOTE_SCRIPT_DIR


class BandwidthTestController:
    RESULT_FILE = "bandwidth_result.json"

    def __init__(self, ssh_client, log_callback=None, progress_callback=None):
        self.ssh = ssh_client
        self.log = log_callback or (lambda msg: None)
        self.progress = progress_callback or (lambda pct, msg: None)
        self.results = {}

    def run(
        self,
        model_weight_dir,
        dp,
        tp,
        kv_cache_dir,
        request_len,
        concurrency,
        output_dir,
    ):
        self.progress(0, "starting bandwidth test ...")
        self.log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] bandwidth test started")
        self.log(f"  model_weight_dir: {model_weight_dir}")
        self.log(f"  dp={dp}, tp={tp}")
        self.log(f"  kv_cache_dir: {kv_cache_dir}")
        self.log(f"  request_len={request_len}, concurrency={concurrency}")

        if not self.ssh or not self.ssh.connected:
            self.log("ERROR: SSH not connected")
            return None

        self.progress(5, "uploading test script to remote host...")
        self._upload_scripts()

        self.progress(10, "checking environment...")
        self._check_remote_env()

        self.progress(15, "launching vLLM server...")
        self._launch_vllm(model_weight_dir, dp, tp, kv_cache_dir)

        self.progress(40, "running bandwidth benchmark...")
        bw = self._run_benchmark(request_len, concurrency)

        self.progress(80, "stopping vLLM server...")
        self._stop_vllm()

        self.progress(90, "collecting results...")
        self._collect_results(bw, output_dir)

        self.progress(100, "bandwidth test complete")
        self.log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] bandwidth test finished, bw={bw:.2f} GB/s")
        return self.results

    def _upload_scripts(self):
        local_script = os.path.join(REMOTE_SCRIPT_DIR, "remote_bench.py")
        if not os.path.exists(local_script):
            self.log("WARNING: remote_bench.py not found, generating dynamically...")
            script_content = self._generate_bench_script()
            self.ssh.execute(f"cat > /tmp/remote_bench.py << 'PYEOF'\n{script_content}\nPYEOF\n")
        else:
            self.ssh.upload_file(local_script, "/tmp/remote_bench.py")
        self.log("script uploaded to /tmp/remote_bench.py")

    def _check_remote_env(self):
        code, out, err = self.ssh.execute("python3 -c 'import torch; print(torch.cuda.is_available())'")
        if code != 0 or "True" not in out:
            self.log(f"WARNING: CUDA torch check failed, code={code}, out={out}, err={err}")

        code, out, err = self.ssh.execute("which vllm || pip show vllm", timeout=30)
        if code != 0:
            self.log("WARNING: vLLM may not be installed")

        code, out, err = self.ssh.execute("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", timeout=15)
        if code == 0:
            self.log(f"GPU: {out.strip()}")

    def _launch_vllm(self, model_dir, dp, tp, kv_cache_dir):
        stop_cmd = "pkill -f 'vllm.entrypoints' || true"
        self.ssh.execute(stop_cmd, timeout=10)
        time.sleep(2)

        cmd = (
            f"python3 -m vllm.entrypoints.openai.api_server "
            f"--model {model_dir} "
            f"--tensor-parallel-size {tp} "
            f"--data-parallel-size {dp} "
            f"--max-model-len 32768 "
            f"--gpu-memory-utilization 0.95 "
            f">> /tmp/vllm_server.log 2>&1 &"
        )
        self.log(f"launching vLLM: {cmd}")
        self.ssh.execute(cmd, timeout=10)
        self.log("waiting for vLLM server to be ready...")

        for i in range(60):
            time.sleep(2)
            code, out, _ = self.ssh.execute("curl -s http://localhost:8000/health", timeout=5)
            if code == 0:
                self.log("vLLM server is ready")
                self.progress(20 + (i / 60) * 20, "vLLM server ready")
                return
            if (i + 1) % 5 == 0:
                self.log(f"  still waiting... ({i * 2}s)")

        self.log("WARNING: vLLM server may not have started in time")

    def _run_benchmark(self, request_len, concurrency):
        bench_cmd = (
            f"python3 /tmp/remote_bench.py "
            f"--host localhost --port 8000 "
            f"--request-len {request_len} "
            f"--concurrency {concurrency} "
            f"--output /tmp/bench_result.json"
        )
        self.log(f"running benchmark: {bench_cmd}")

        def _on_out(line):
            self.log(f"  [remote] {line}")

        code, out, err = self.ssh.execute(bench_cmd, on_stdout=_on_out, timeout=1800)
        if code != 0:
            self.log(f"benchmark failed: exit={code}, err={err}")
            return self._estimate_bandwidth_from_logs()

        code, out, err = self.ssh.execute("cat /tmp/bench_result.json", timeout=10)
        if code == 0 and out.strip():
            try:
                data = json.loads(out)
                bw = float(data.get("bandwidth_gbs", data.get("bandwidth", 0)))
                self.results["bench_result"] = data
                return bw
            except (json.JSONDecodeError, ValueError):
                pass
        return self._estimate_bandwidth_from_logs()

    def _estimate_bandwidth_from_logs(self):
        self.log("estimating bandwidth from server logs...")
        code, out, _ = self.ssh.execute(
            r"grep -i 'throughput\|bandwidth\|tokens/s\|tok/s' /tmp/vllm_server.log | tail -20",
            timeout=10,
        )
        if out:
            self.log(f"log excerpts: {out[:2000]}")
            nums = re.findall(r"([\d.]+)\s*(?:tokens/s|tok/s)", out)
            if nums:
                tok_per_s = max(float(n) for n in nums)
                bw = tok_per_s * 8 * 2 / 1e9
                self.log(f"estimated bandwidth: {bw:.2f} GB/s (from {tok_per_s:.0f} tok/s)")
                return bw
        self.log("WARNING: could not determine bandwidth, using default")
        return 0.0

    def _stop_vllm(self):
        self.log("stopping vLLM server...")
        self.ssh.execute("pkill -f 'vllm.entrypoints' || true", timeout=10)
        time.sleep(3)

    def _collect_results(self, bw, output_dir):
        self.results["bandwidth_gbs"] = bw
        self.results["timestamp"] = datetime.now().isoformat()
        local_result_file = os.path.join(output_dir, self.RESULT_FILE)
        os.makedirs(output_dir, exist_ok=True)
        with open(local_result_file, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        self.log(f"results saved to {local_result_file}")

    @staticmethod
    def _generate_bench_script():
        return r'''
import argparse, json, time, random, threading, requests

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--request-len", type=int, default=1024)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--output", default="/tmp/bench_result.json")
    args = p.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    models = requests.get(f"{base_url}/v1/models", timeout=10).json()
    model = models["data"][0]["id"]
    print(f"Model: {model}")

    prompt = "hello " * args.request_len
    total_tokens = 0
    total_time = 0
    lock = threading.Lock()
    errors = []

    def worker():
        nonlocal total_tokens, total_time
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": 1,
            "temperature": 0,
        }
        t0 = time.time()
        try:
            r = requests.post(f"{base_url}/v1/completions", json=payload, timeout=300)
            if r.status_code == 200:
                data = r.json()
                tokens = data.get("usage", {}).get("prompt_tokens", args.request_len)
                with lock:
                    total_tokens += tokens
                    total_time += time.time() - t0
            else:
                errors.append(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=worker) for _ in range(args.concurrency)]
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start

    tok_per_s = total_tokens / max(elapsed, 0.001) if total_tokens > 0 else 0
    avg_latency = total_time / max(args.concurrency, 1) if total_tokens > 0 else 0
    bandwidth_gbs = tok_per_s * 8 * 2 / 1e9  # approximate: 2 bytes per token for FP16

    result = {
        "model": model,
        "request_len": args.request_len,
        "concurrency": args.concurrency,
        "total_tokens": total_tokens,
        "elapsed_s": elapsed,
        "tokens_per_s": tok_per_s,
        "bandwidth_gbs": bandwidth_gbs,
        "avg_latency_s": avg_latency,
        "errors": errors[:10],
    }
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
'''
