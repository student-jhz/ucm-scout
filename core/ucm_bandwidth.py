import json
import os
import time
from datetime import datetime
from config import REMOTE_SCRIPT_DIR


class UcmBandwidthController:
    RESULT_FILE = "ucm_bandwidth_result.json"
    BLOCK_SIZE = 128
    ELEM_SIZE = 2
    REMOTE_PKG_DIR = "/tmp/ucm_pkgs"

    def __init__(self, ssh_client, log_callback=None, progress_callback=None):
        self.ssh = ssh_client
        self.log = log_callback or (lambda msg: None)
        self.progress = progress_callback or (lambda pct, msg: None)
        self.results = {}

    def get_docker_images(self):
        code, out, err = self.ssh.execute(
            "docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -iE 'vllm'",
            timeout=15,
        )
        if code != 0 and not out.strip():
            return []
        return [line.strip() for line in out.strip().split("\n") if line.strip()]

    def parse_model_config(self, model_path):
        config_path = os.path.join(model_path, "config.json").replace("\\", "/")
        code, out, err = self.ssh.execute(f"cat {config_path}", timeout=15)
        if code != 0 or not out.strip():
            self.log(f"ERROR: cannot read config.json from {config_path}: {err}")
            return None

        try:
            config = json.loads(out)
        except json.JSONDecodeError:
            self.log("ERROR: invalid config.json")
            return None

        num_layers = config.get("num_hidden_layers", 0)
        model_type = config.get("model_type", "").lower()

        is_mla = "deepseek" in model_type or "kv_lora_rank" in config

        if is_mla:
            kv_lora_rank = config.get("kv_lora_rank", 512)
            qk_rope_head_dim = config.get("qk_rope_head_dim", 64)
            head_dim = kv_lora_rank + qk_rope_head_dim
        else:
            num_kv_heads = config.get("num_key_value_heads", config.get("num_attention_heads", 32))
            head_dim = config.get("head_dim", config.get("hidden_size", 4096) // config.get(
                "num_attention_heads", 32))
            head_dim = num_kv_heads * head_dim * 2

        if not num_layers or not head_dim:
            self.log(f"ERROR: missing config fields - layers={num_layers}, head_dim={head_dim}")
            return None

        shard_size = head_dim * self.BLOCK_SIZE * self.ELEM_SIZE
        shard_number = num_layers

        self.log(f"model: {model_type}, layers={num_layers}, "
                 f"shard_size={shard_size}B ({shard_size / 1024:.1f}KB), "
                 f"shard_number={shard_number}")
        return shard_size, shard_number

    def run(self, model_path, docker_image, ucm_pkg_local, dep_whl_local,
            storage_backend, request_len, output_dir):
        self.progress(0, "starting UCM bandwidth test...")
        self.log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] UCM bandwidth test started")
        self.log(f"  model_path: {model_path}")
        self.log(f"  docker_image: {docker_image}")
        self.log(f"  storage_backend: {storage_backend}")
        self.log(f"  request_len: {request_len}")

        if not self.ssh or not self.ssh.connected:
            self.log("ERROR: SSH not connected")
            return None

        cfg = self.parse_model_config(model_path)
        if not cfg:
            return None
        shard_size, shard_number = cfg
        block_number = max(1, request_len // self.BLOCK_SIZE)
        self.log(f"  shard_size={shard_size}B, shard_number={shard_number}, "
                 f"block_number={block_number} (req_len/{self.BLOCK_SIZE})")

        self.progress(5, "uploading packages...")
        self._upload_packages(ucm_pkg_local, dep_whl_local)

        self.progress(10, "creating container...")
        container_id = self._create_container(docker_image, model_path, storage_backend)
        if not container_id:
            return None

        self.progress(20, "installing UCM in container...")
        if not self._install_ucm(container_id, dep_whl_local, ucm_pkg_local):
            self._stop_container(container_id)
            return None

        self.progress(40, "uploading benchmark script...")
        self._upload_bench_script()

        self.progress(50, "running UCM benchmark...")
        bw_result = self._run_benchmark(container_id, shard_size, shard_number,
                                        block_number, storage_backend)
        if not bw_result:
            self._stop_container(container_id)
            return None

        self.progress(85, "stopping container...")
        self._stop_container(container_id)

        self.progress(95, "collecting results...")
        self._collect_results(bw_result, shard_size, shard_number, block_number, output_dir)

        self.progress(100, "UCM bandwidth test complete")
        self.log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] bandwidth test finished")
        return self.results

    def _upload_packages(self, ucm_pkg_local, dep_whl_local):
        self.log("uploading packages to remote...")
        pkg_name = os.path.basename(ucm_pkg_local)
        dep_name = os.path.basename(dep_whl_local)
        self.ssh.execute(f"mkdir -p {self.REMOTE_PKG_DIR}", timeout=10)
        self.ssh.upload_file(ucm_pkg_local, f"{self.REMOTE_PKG_DIR}/{pkg_name}")
        self.log(f"  uploaded {pkg_name}")
        self.ssh.upload_file(dep_whl_local, f"{self.REMOTE_PKG_DIR}/{dep_name}")
        self.log(f"  uploaded {dep_name}")

    def _create_container(self, docker_image, model_path, storage_backend):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        container_name = f"ucm_bench_{timestamp}"

        model_path = model_path.replace("\\", "/")
        storage_backend = storage_backend.replace("\\", "/")
        remote_pkg = self.REMOTE_PKG_DIR.replace("\\", "/")

        cmd = (
            f"docker run -d --rm --gpus all "
            f"-v {model_path}:{model_path} "
            f"-v {storage_backend}:{storage_backend} "
            f"-v {remote_pkg}:{remote_pkg} "
            f"--name {container_name} "
            f"{docker_image} sleep infinity"
        )
        self.log(f"creating container: {cmd}")
        code, out, err = self.ssh.execute(cmd, timeout=30)
        container_id = out.strip()
        if code != 0:
            self.log(f"ERROR: failed to create container: {err}")
            return None
        self.log(f"container created: {container_id}")
        self.results["container_id"] = container_id
        return container_id

    def _install_ucm(self, container_id, dep_whl_local, ucm_pkg_local):
        dep_name = os.path.basename(dep_whl_local)
        pkg_name = os.path.basename(ucm_pkg_local)
        remote_pkg = self.REMOTE_PKG_DIR

        self.log("installing dependencies...")
        cmds = [
            f"docker exec {container_id} pip install {remote_pkg}/{dep_name}",
            f"docker exec {container_id} pip install {remote_pkg}/{pkg_name}",
        ]

        for cmd in cmds:
            self.log(f"  $ {cmd}")
            code, out, err = self.ssh.execute(cmd, timeout=120)
            if out.strip():
                for line in out.strip().split("\n"):
                    self.log(f"    {line}")
            if code != 0:
                self.log(f"ERROR: install failed: {err}")
                return False
        self.log("UCM installed successfully")
        return True

    def _upload_bench_script(self):
        local_script = os.path.join(REMOTE_SCRIPT_DIR, "ucm_bench.py")
        self.ssh.upload_file(local_script, f"{self.REMOTE_PKG_DIR}/ucm_bench.py")
        self.log("benchmark script uploaded")

    def _run_benchmark(self, container_id, shard_size, shard_number,
                       block_number, storage_backend):
        remote_pkg = self.REMOTE_PKG_DIR
        bench_cmd = (
            f"docker exec {container_id} python3 {remote_pkg}/ucm_bench.py "
            f"--shard-size {shard_size} "
            f"--shard-number {shard_number} "
            f"--block-number {block_number} "
            f"--storage-backend {storage_backend} "
            f"--output {remote_pkg}/ucm_bench_result.json"
        )
        self.log(f"running benchmark: {bench_cmd}")

        def on_out(line):
            self.log(f"  [bench] {line}")

        code, out, err = self.ssh.execute(bench_cmd, on_stdout=on_out, timeout=600)
        if code != 0:
            self.log(f"benchmark failed: exit={code}, err={err}")
            return None

        code, out, err = self.ssh.execute(
            f"cat {remote_pkg}/ucm_bench_result.json", timeout=10
        )
        if code == 0 and out.strip():
            try:
                return json.loads(out)
            except json.JSONDecodeError:
                self.log("ERROR: invalid benchmark result JSON")
        return None

    def _stop_container(self, container_id):
        self.log(f"stopping container {container_id}...")
        self.ssh.execute(f"docker stop {container_id}", timeout=30)
        self.log("container stopped")

    def _collect_results(self, bw_result, shard_size, shard_number,
                         block_number, output_dir):
        self.results.update({
            "shard_size": shard_size,
            "shard_number": shard_number,
            "block_number": block_number,
            "block_size": self.BLOCK_SIZE,
            "dump_avg_bw_gbs": bw_result.get("dump_avg_bw_gbs", 0),
            "dump_p99_bw_gbs": bw_result.get("dump_p99_bw_gbs", 0),
            "load_avg_bw_gbs": bw_result.get("load_avg_bw_gbs", 0),
            "load_p99_bw_gbs": bw_result.get("load_p99_bw_gbs", 0),
            "timestamp": datetime.now().isoformat(),
        })

        os.makedirs(output_dir, exist_ok=True)
        result_path = os.path.join(output_dir, self.RESULT_FILE)
        with open(result_path, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        self.log(f"results saved to {result_path}")
