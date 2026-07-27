import json
import re
import time
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


class MockSSHClient:
    def __init__(self, host, port=22, username="", password=""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._connected = False

    def connect(self, timeout=None):
        time.sleep(0.5)
        self._connected = True

    def disconnect(self):
        self._connected = False

    @property
    def connected(self):
        return self._connected

    def upload_file(self, local_path, remote_path):
        pass

    def execute(self, command, on_stdout=None, on_stderr=None, timeout=600):
        if "echo ok" in command and "uname" in command:
            return 0, "Linux demo-host 5.15.0-generic x86_64 GNU/Linux\n", ""

        if "ls -1p" in command:
            return 0, "bin/\ndev/\netc/\nhome/\nmodels/\nroot/\ntmp/\nusr/\nvar/\n", ""

        if "docker images" in command:
            return 0, "nvidia/cuda:12.1-vllm\nvllm/vllm-openai:latest\nvllm-ascend:0.6.0\n", ""

        if "config.json" in command and "cat" in command:
            model_config = json.dumps({
                "model_type": "llama",
                "num_hidden_layers": 32,
                "num_attention_heads": 32,
                "num_key_value_heads": 8,
                "head_dim": 128,
                "hidden_size": 4096,
                "torch_dtype": "float16",
            })
            return 0, model_config, ""

        if "mkdir" in command and "ucm_pkgs" in command:
            return 0, "", ""

        if "tar -xzf" in command and "ucm_pkgs" in command:
            return 0, "", ""

        if "find" in command and "*.whl" in command:
            return 0, "/tmp/ucm_pkgs/_extracted/ucm_manager-0.1.0-py3-none-any.whl\n", ""

        if "docker run" in command and "sleep infinity" in command:
            return 0, "demo-container-001\n", ""

        if "docker exec" in command and "pip install" in command:
            if on_stdout:
                on_stdout("Successfully installed unified-cache-management")
            return 0, "Successfully installed\n", ""

        if "docker exec" in command and "python3" in command and "ucm_bench.py" in command:
            if on_stdout:
                on_stdout("[demo] running UCM benchmark...")
            time.sleep(1.0)
            result = {
                "shard_size": 288,
                "shard_number": 32,
                "block_number": 8,
                "total_size_bytes": 288 * 32 * 8,
                "dump_epochs": 8,
                "load_epochs": 8,
                "dump_avg_bw_gbs": random.uniform(2.5, 4.0),
                "dump_p99_bw_gbs": random.uniform(2.0, 3.5),
                "load_avg_bw_gbs": random.uniform(3.0, 5.0),
                "load_p99_bw_gbs": random.uniform(2.5, 4.5),
            }
            result_text = json.dumps(result, indent=2)
            if on_stdout:
                on_stdout(result_text)
            return 0, result_text, ""

        if "cat" in command and "ucm_bench_result.json" in command:
            return 0, json.dumps({
                "shard_size": 288,
                "shard_number": 32,
                "block_number": 8,
                "total_size_bytes": 288 * 32 * 8,
                "dump_epochs": 8,
                "load_epochs": 8,
                "dump_avg_bw_gbs": 3.2,
                "dump_p99_bw_gbs": 2.8,
                "load_avg_bw_gbs": 4.1,
                "load_p99_bw_gbs": 3.6,
            }), ""

        if "docker stop" in command:
            return 0, "demo-container-001\n", ""

        if "torch.cuda" in command:
            return 0, "True\n", ""

        if "which vllm" in command or "pip show vllm" in command:
            return 0, "vllm 0.6.0 (simulated)\n", ""

        if "nvidia-smi" in command:
            return 0, "Tesla V100-SXM2-32GB, 32768 MiB\nTesla V100-SXM2-32GB, 32768 MiB\n", ""

        if "curl" in command and "health" in command:
            return 0, "ok", ""

        if "pkill" in command:
            return 0, "", ""

        if "vllm.entrypoints" in command and ".py" in command:
            time.sleep(0.3)
            return 0, "", ""

        if "cat > /tmp/remote_bench.py" in command:
            return 0, "", ""

        if "remote_bench.py" in command:
            if on_stdout:
                on_stdout("[demo] starting benchmark...")
            time.sleep(1.5)
            match_concurrency = re.search(r"--concurrency\s+(\d+)", command)
            concurrency = int(match_concurrency.group(1)) if match_concurrency else 1
            tokens_per_second = random.uniform(1800, 2500) * concurrency
            elapsed = random.uniform(0.3, 0.8) / max(concurrency, 1)
            total_tokens = int(tokens_per_second * elapsed)
            bandwidth_gbs = tokens_per_second * 8 * 2 / 1e9
            result = {
                "model": "demo-model-7b",
                "request_len": 1024,
                "concurrency": concurrency,
                "total_tokens": total_tokens,
                "elapsed_s": elapsed,
                "tokens_per_s": tokens_per_second,
                "bandwidth_gbs": bandwidth_gbs,
                "avg_latency_s": elapsed,
                "errors": [],
            }
            result_text = json.dumps(result, indent=2)
            if on_stdout:
                on_stdout(result_text)
            return 0, result_text, ""

        if "cat /tmp/bench_result.json" in command:
            return 0, json.dumps({
                "model": "demo-model-7b",
                "request_len": 1024,
                "concurrency": 1,
                "total_tokens": 1024,
                "elapsed_s": 0.5,
                "tokens_per_s": 2048.0,
                "bandwidth_gbs": 2048 * 8 * 2 / 1e9,
                "avg_latency_s": 0.5,
                "errors": [],
            }), ""

        if "grep" in command and ("throughput" in command or "vllm_server.log" in command):
            return 0, "Avg throughput: 2048.5 tokens/s\n", ""

        return 0, "ok\n", ""

    def test_connection(self):
        return True, "Linux demo-host 5.15.0-generic x86_64 GNU/Linux (simulated)"


class _MockVLLMHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/health", "/health/"):
            self._respond(200, "ok", "text/plain")
        elif self.path.startswith("/v1/models"):
            self._respond(200, json.dumps({"data": [{"id": "demo-model-7b"}]}))
        else:
            self._respond(404, "not found", "text/plain")

    def do_POST(self):
        if self.path.startswith("/v1/completions"):
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}
            prompt_tokens = body.get("prompt", "").count("hello") + 1 or 1024
            max_tokens = body.get("max_tokens", 1)
            is_stream = body.get("stream", False)

            processing_time = random.uniform(0.1, 0.4)

            if is_stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                time.sleep(processing_time)
                first = {
                    "id": "cmpl-demo",
                    "object": "text_completion",
                    "created": int(time.time()),
                    "model": "demo-model-7b",
                    "choices": [{"text": "Hello", "index": 0, "finish_reason": None}],
                    "usage": None,
                }
                self.wfile.write(f"data: {json.dumps(first)}\n\n".encode())
                self.wfile.flush()

                d = {"id": "cmpl-demo", "object": "text_completion", "created": int(time.time()),
                     "model": "demo-model-7b",
                     "choices": [{"text": "", "index": 0, "finish_reason": "length"}],
                     "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": max_tokens,
                               "total_tokens": prompt_tokens + max_tokens}}
                self.wfile.write(f"data: {json.dumps(d)}\n\n".encode())
                self.wfile.write("data: [DONE]\n\n".encode())
                self.wfile.flush()
            else:
                time.sleep(processing_time)
                resp = {
                    "id": "cmpl-demo",
                    "object": "text_completion",
                    "created": int(time.time()),
                    "model": "demo-model-7b",
                    "choices": [{"text": "Hello world", "index": 0, "finish_reason": "length"}],
                    "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": max_tokens,
                              "total_tokens": prompt_tokens + max_tokens},
                }
                self._respond(200, json.dumps(resp))
        else:
            self._respond(404, "not found", "text/plain")

    def _respond(self, code, body, content_type="application/json"):
        body = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


class MockVLLMServer:
    def __init__(self, host="127.0.0.1", port=8000):
        self.host = host
        self.port = port
        self._server = None
        self._thread = None

    def start(self):
        self._server = HTTPServer((self.host, self.port), _MockVLLMHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None

    @property
    def running(self):
        return self._server is not None


_demo_server = MockVLLMServer()


def start_demo():
    _demo_server.start()


def stop_demo():
    _demo_server.stop()


def is_demo_running():
    return _demo_server.running
