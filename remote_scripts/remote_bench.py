import argparse
import json
import time
import random
import threading
import requests


def main():
    p = argparse.ArgumentParser(description="UCM Bandwidth Benchmark")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--request-len", type=int, default=1024)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--output", default="/tmp/bench_result.json")
    args = p.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    resp = requests.get(f"{base_url}/v1/models", timeout=10)
    models = resp.json()
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
