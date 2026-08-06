import json
import time
import threading
import requests
from datetime import datetime


class TTFTTestController:
    def __init__(self, log_callback=None, progress_callback=None):
        self.log = log_callback or (lambda msg: None)
        self.progress = progress_callback or (lambda pct, msg: None)
        self.results = {}

    def run_online(self, service_url, model_path, model_name, request_len, concurrency):
        self.progress(0, "starting online TTFT test...")
        self.log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] TTFT online test started")
        self.log(f"  service_url: {service_url}")
        self.log(f"  model: {model_name}")
        self.log(f"  request_len={request_len}, concurrency={concurrency}")

        base_url = service_url.rstrip("/")
        self.progress(10, "checking service health...")
        try:
            r = requests.get(f"{base_url}/health", timeout=10)
            self.log(f"  service health: {r.status_code}")
        except Exception as e:
            self.log(f"ERROR: cannot reach service: {e}")
            return None

        self.progress(20, "testing full prefill (cold start)...")
        full_ttft = self._measure_ttft(base_url, model_name, request_len, concurrency, warmup=False)

        self.progress(50, "testing HBM PC hit (warm cache)...")
        self._warmup_cache(base_url, model_name, request_len)
        hbm_ttft = self._measure_ttft(base_url, model_name, request_len, concurrency, warmup=True)

        self.progress(90, "collecting results...")
        self.results = {
            "mode": "online",
            "service_url": service_url,
            "model_name": model_name,
            "model_path": model_path,
            "request_len": request_len,
            "concurrency": concurrency,
            "full_prefill_ttft_ms": full_ttft,
            "hbm_pc_ttft_ms": hbm_ttft,
            "timestamp": datetime.now().isoformat(),
        }
        self.progress(100, "TTFT online test complete")
        self.log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] TTFT test finished")
        self.log(f"  full_prefill_ttft={full_ttft:.2f}ms, hbm_pc_ttft={hbm_ttft:.2f}ms")
        return self.results

    def _measure_ttft(self, base_url, model_name, request_len, concurrency, warmup=False):
        prompt = "hello " * request_len
        ttft_values = []
        errors = []
        lock = threading.Lock()

        def worker():
            payload = {
                "model": model_name,
                "prompt": prompt,
                "max_tokens": 1,
                "temperature": 0,
                "stream": True,
            }
            try:
                t0 = time.time()
                r = requests.post(
                    f"{base_url}/v1/completions",
                    json=payload,
                    timeout=300,
                    stream=True,
                )
                first_token_time = None
                line_count = 0
                for line in r.iter_lines(decode_unicode=True):
                    line_count += 1
                    if line_count <= 3:
                        self.log(f"    [debug] line {line_count}: {line[:100]}")
                    if line and line.startswith("data: ") and not first_token_time:
                        first_token_time = time.time()
                        break
                if first_token_time:
                    ttft = (first_token_time - t0) * 1000
                    with lock:
                        ttft_values.append(ttft)
                else:
                    errors.append(f"No response data received (got {line_count} lines)")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(concurrency)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            self.log(f"  errors: {errors[:5]}")

        if ttft_values:
            avg = sum(ttft_values) / len(ttft_values)
            self.log(f"  measured {len(ttft_values)} TTFT values, avg={avg:.2f}ms")
            return avg
        else:
            self.log("WARNING: could not measure TTFT")
            return 0.0

    def _warmup_cache(self, base_url, model_name, request_len):
        self.log("  warming up cache...")
        prompt = "hello " * request_len
        try:
            requests.post(
                f"{base_url}/v1/completions",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "max_tokens": 1,
                    "temperature": 0,
                },
                timeout=60,
            )
        except Exception:
            pass
        time.sleep(1)

    def save_results(self, output_dir):
        import os
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "ttft_result.json")
        with open(path, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        self.log(f"TTFT results saved to {path}")
        return path
