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
    EXTRACT_DIR = "/tmp/ucm_pkgs/_extracted"

    def __init__(self, ssh_client, log_callback=None, progress_callback=None):
        self.ssh = ssh_client
        self.log = log_callback or (lambda msg: None)
        self.progress = progress_callback or (lambda pct, msg: None)
        self.results = {}

    def _detect_device_type(self):
        self.log("[device] detecting device type...")
        code, out, _ = self.ssh.execute(
            "command -v nvidia-smi >/dev/null 2>&1 && echo NVIDIA || true", timeout=5
        )
        if "NVIDIA" in out:
            self.log("[device] OK: NVIDIA GPU detected")
            return "nvidia"

        code, out, _ = self.ssh.execute(
            "command -v npu-smi >/dev/null 2>&1 && echo ASCEND || true", timeout=5
        )
        if "ASCEND" in out:
            self.log("[device] OK: Ascend NPU detected")
            return "ascend"

        code, out, _ = self.ssh.execute(
            "ls /dev/davinci* >/dev/null 2>&1 && echo ASCEND || true", timeout=5
        )
        if "ASCEND" in out:
            self.log("[device] OK: Ascend NPU detected (davinci)")
            return "ascend"

        self.log("[device] WARN: unknown device type, defaulting to nvidia")
        return "nvidia"

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
        self.log(f"[config] reading {config_path} ...")
        code, out, err = self.ssh.execute(f"cat {config_path}", timeout=15)
        if code != 0 or not out.strip():
            self.log(f"[config] FAIL: cannot read config.json")
            self.log(f"[config]   reason: {err.strip() if err else 'file not found or empty'}")
            return None

        try:
            config = json.loads(out)
        except json.JSONDecodeError as e:
            self.log(f"[config] FAIL: invalid JSON - {e}")
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
            self.log(f"[config] FAIL: missing fields - num_hidden_layers={num_layers}, "
                     f"computed_head_dim={head_dim}")
            return None

        shard_size = head_dim * self.BLOCK_SIZE * self.ELEM_SIZE
        shard_number = num_layers

        self.log(f"[config] OK: type={model_type}, layers={num_layers}, "
                 f"shard_size={shard_size}B ({shard_size / 1024:.1f}KB), "
                 f"shard_number={shard_number}")
        return shard_size, shard_number

    def run(self, model_path, docker_image, ucm_pkg_local, dep_whl_local,
            storage_backend, request_len, tp, output_dir):
        self.log(f"{'='*50}")
        self.log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] UCM bandwidth test started")
        self.log(f"  model_path: {model_path}")
        self.log(f"  docker_image: {docker_image}")
        self.log(f"  storage_backend: {storage_backend}")
        self.log(f"  ucm_pkg: {os.path.basename(ucm_pkg_local)}")
        self.log(f"  dep_whl: {os.path.basename(dep_whl_local)}")
        self.log(f"  request_len: {request_len}, tp: {tp}")

        if not self.ssh or not self.ssh.connected:
            self.log("[init] FAIL: SSH not connected")
            return None

        self.log("[init] OK: SSH connected")

        device_type = self._detect_device_type()

        temp_dir = self._check_and_prepare_storage(storage_backend)
        if not temp_dir:
            return None
        actual_storage = temp_dir

        cfg = self.parse_model_config(model_path)
        if not cfg:
            self._cleanup_storage(temp_dir)
            return None
        shard_size, shard_number = cfg
        block_number = max(1, request_len // self.BLOCK_SIZE)
        self.log(f"[calc] shard_size={shard_size}B, shard_number={shard_number}, "
                 f"block_number={block_number} (req_len/{self.BLOCK_SIZE})")

        self.progress(5, "uploading packages...")
        if not self._upload_packages(ucm_pkg_local, dep_whl_local):
            self._cleanup_storage(temp_dir)
            return None

        self.progress(10, "extracting UCM package...")
        if not self._extract_ucm(ucm_pkg_local):
            self._cleanup_storage(temp_dir)
            return None

        self.progress(15, "creating container...")
        container_id = self._create_container(docker_image, model_path, actual_storage, device_type)
        if not container_id:
            self._cleanup_storage(temp_dir)
            return None

        self.progress(25, "installing wrapt dependency...")
        if not self._install_wrapt(container_id, dep_whl_local):
            self._stop_container(container_id)
            self._cleanup_storage(temp_dir)
            return None

        self.progress(35, "installing UCM in container...")
        if not self._install_ucm_whl(container_id):
            self._stop_container(container_id)
            self._cleanup_storage(temp_dir)
            return None

        self.progress(45, "uploading benchmark script...")
        if not self._upload_bench_script():
            self._stop_container(container_id)
            self._cleanup_storage(temp_dir)
            return None

        self.progress(50, "running UCM benchmark...")
        bw_result = self._run_benchmark(container_id, shard_size, shard_number,
                                        block_number, actual_storage, tp, device_type)
        if not bw_result:
            self._stop_container(container_id)
            self._cleanup_storage(temp_dir)
            return None

        self.progress(85, "stopping container...")
        self._stop_container(container_id)

        self.progress(90, "cleaning up storage...")
        self._cleanup_storage(temp_dir)

        self.progress(95, "collecting results...")
        self._collect_results(bw_result, shard_size, shard_number, block_number, output_dir)

        self.progress(100, "UCM bandwidth test complete")
        self.log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ====== ALL DONE ======")
        return self.results

    def _check_and_prepare_storage(self, storage_backend):
        storage_backend = storage_backend.rstrip("/")
        self.log(f"[storage] checking path: {storage_backend}")

        code, out, err = self.ssh.execute(
            f"test -d {storage_backend} && echo 'EXISTS' || echo 'NOT_EXISTS'", timeout=10
        )
        if "NOT_EXISTS" in out:
            self.log(f"[storage] FAIL: path does not exist: {storage_backend}")
            return None

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        temp_dir = f"{storage_backend}/ucm_bench_{timestamp}"
        self.log(f"[storage] OK: creating temp dir {temp_dir}")
        code, out, err = self.ssh.execute(f"mkdir -p {temp_dir}", timeout=10)
        if code != 0:
            self.log(f"[storage] FAIL: cannot create {temp_dir}: {err}")
            return None
        self.log(f"[storage] OK: temp dir created, data will be cleaned up after test")
        return temp_dir

    def _cleanup_storage(self, temp_dir):
        self.log(f"[storage] cleaning up {temp_dir} ...")
        code, out, err = self.ssh.execute(f"rm -rf {temp_dir}", timeout=10)
        if code != 0:
            self.log(f"[storage] warn: cleanup failed: {err}")
        else:
            self.log(f"[storage] OK: removed")

    def _upload_packages(self, ucm_pkg_local, dep_whl_local):
        pkg_name = os.path.basename(ucm_pkg_local)
        dep_name = os.path.basename(dep_whl_local)

        self.log(f"[upload] creating {self.REMOTE_PKG_DIR} ...")
        self.ssh.execute(f"mkdir -p {self.REMOTE_PKG_DIR}", timeout=10)

        try:
            self.ssh.upload_file(ucm_pkg_local, f"{self.REMOTE_PKG_DIR}/{pkg_name}")
            self.log(f"[upload] OK: {pkg_name}")
        except Exception as e:
            self.log(f"[upload] FAIL: {pkg_name} - {e}")
            return False

        try:
            self.ssh.upload_file(dep_whl_local, f"{self.REMOTE_PKG_DIR}/{dep_name}")
            self.log(f"[upload] OK: {dep_name}")
        except Exception as e:
            self.log(f"[upload] FAIL: {dep_name} - {e}")
            return False

        return True

    def _extract_ucm(self, ucm_pkg_local):
        pkg_name = os.path.basename(ucm_pkg_local)
        rp = self.REMOTE_PKG_DIR

        self.log(f"[extract] extracting {pkg_name} ...")
        code, out, err = self.ssh.execute(
            f"mkdir -p {self.EXTRACT_DIR} && "
            f"tar -xzf {rp}/{pkg_name} -C {self.EXTRACT_DIR}",
            timeout=30,
        )
        if code != 0:
            self.log(f"[extract] FAIL: tar extract failed")
            self.log(f"[extract]   reason: {err.strip() if err else 'unknown'}")
            return False

        code, out, err = self.ssh.execute(
            f"find {self.EXTRACT_DIR} -name '*.whl' -type f", timeout=10,
        )
        if code != 0 or not out.strip():
            self.log(f"[extract] FAIL: no .whl found inside {pkg_name}")
            return False

        whl_files = [line.strip() for line in out.strip().split("\n") if line.strip()]
        self.log(f"[extract] OK: found {len(whl_files)} whl(s)")
        for w in whl_files:
            self.log(f"[extract]   {w}")
        self._extracted_whls = whl_files
        return True

    def _create_container(self, docker_image, model_path, storage_backend, device_type):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        container_name = f"ucm_bench_{timestamp}"

        model_path = model_path.replace("\\", "/")
        storage_backend = storage_backend.replace("\\", "/")
        remote_pkg = self.REMOTE_PKG_DIR.replace("\\", "/")

        volumes = (
            f"-v {model_path}:{model_path} "
            f"-v {storage_backend}:{storage_backend} "
            f"-v {remote_pkg}:{remote_pkg} "
        )

        if device_type == "ascend":
            code, dev_out, _ = self.ssh.execute("ls -d /dev/davinci* 2>/dev/null", timeout=5)
            davinci_devices = [d.strip() for d in dev_out.strip().split("\n") if d.strip()]

            self.log(f"[container] Ascend devices: {davinci_devices}")
            devices = " ".join(f"--device {d}" for d in davinci_devices)
            devices += " --device /dev/devmm_svm --device /dev/hisi_hdc"

            ascend_volumes = (
                "-v /usr/local/dcmi:/usr/local/dcmi:ro "
                "-v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/:ro "
                "-v /usr/local/Ascend/driver/tools/hccn_tool:/usr/local/Ascend/driver/tools/hccn_tool:ro "
                "-v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi:ro "
            )

            cmd = (
                f"docker run -d --rm "
                f"{devices} "
                f"--privileged --shm-size=1g "
                f"{volumes} "
                f"{ascend_volumes} "
                f"--name {container_name} "
                f"{docker_image} sleep infinity"
            )
        else:
            cmd = (
                f"docker run -d --rm --gpus all "
                f"{volumes} "
                f"--name {container_name} "
                f"{docker_image} sleep infinity"
            )

        self.log(f"[container] creating ({device_type}): {cmd}")
        code, out, err = self.ssh.execute(cmd, timeout=30)
        container_id = out.strip()
        if code != 0:
            self.log(f"[container] FAIL: docker run failed")
            self.log(f"[container]   reason: {err.strip() if err else 'unknown'}")
            return None
        self.log(f"[container] OK: {container_id}")
        self.results["container_id"] = container_id
        self.results["device_type"] = device_type
        return container_id

    def _install_wrapt(self, container_id, dep_whl_local):
        dep_name = os.path.basename(dep_whl_local)
        rp = self.REMOTE_PKG_DIR
        cmd = f"docker exec {container_id} pip install {rp}/{dep_name}"

        self.log(f"[install] step 1/2: wrapt dependency")
        self.log(f"[install]   $ {cmd}")
        code, out, err = self.ssh.execute(cmd, timeout=120)

        for line in out.strip().split("\n"):
            if line.strip():
                self.log(f"[install]   {line.strip()}")
        if err.strip():
            for line in err.strip().split("\n"):
                if line.strip():
                    self.log(f"[install]   [stderr] {line.strip()}")

        if code != 0:
            self.log(f"[install] FAIL: wrapt installation failed (exit={code})")
            return False
        self.log(f"[install] OK: wrapt installed")
        return True

    def _install_ucm_whl(self, container_id):
        rp = self.REMOTE_PKG_DIR

        if not getattr(self, "_extracted_whls", None):
            self.log(f"[install] FAIL: no extracted whl files found")
            return False

        ucm_whls = [w for w in self._extracted_whls
                     if "wrapt" not in os.path.basename(w).lower()]
        if not ucm_whls:
            self.log(f"[install] FAIL: no UCM whl found (all whls are wrapt)")
            return False

        self.log(f"[install] step 2/2: UCM package")
        ok_all = True
        for whl in ucm_whls:
            cmd = f"docker exec {container_id} pip install {whl}"
            self.log(f"[install]   $ {cmd}")
            code, out, err = self.ssh.execute(cmd, timeout=120)

            for line in out.strip().split("\n"):
                if line.strip():
                    self.log(f"[install]   {line.strip()}")
            if err.strip():
                for line in err.strip().split("\n"):
                    if line.strip():
                        self.log(f"[install]   [stderr] {line.strip()}")

            if code != 0:
                self.log(f"[install] FAIL: {os.path.basename(whl)} install failed (exit={code})")
                ok_all = False
            else:
                self.log(f"[install] OK: {os.path.basename(whl)} installed")

        return ok_all

    def _upload_bench_script(self):
        local_script = os.path.join(REMOTE_SCRIPT_DIR, "ucm_bench.py")
        try:
            self.ssh.upload_file(local_script, f"{self.REMOTE_PKG_DIR}/ucm_bench.py")
            self.log(f"[upload] OK: ucm_bench.py")
            return True
        except Exception as e:
            self.log(f"[upload] FAIL: ucm_bench.py - {e}")
            return False

    def _run_benchmark(self, container_id, shard_size, shard_number,
                       block_number, storage_backend, tp, device_type):
        remote_pkg = self.REMOTE_PKG_DIR
        output_file = f"{remote_pkg}/ucm_bench_result.json"

        ld_preload = ""
        if device_type == "ascend":
            ld_preload = (
                "export UCM_PATH=$(pip show uc-manager 2>/dev/null | "
                "grep Location | awk \"{print \\$2}\"); "
                "export LD_LIBRARY_PATH=$UCM_PATH/ucm/shared/metrics:$LD_LIBRARY_PATH; "
            )

        bench_cmd = (
            f"docker exec {container_id} bash -c '"
            f"{ld_preload}"
            f"PYTHONUNBUFFERED=1 stdbuf -oL python3 {remote_pkg}/ucm_bench.py "
            f"--worker-number {tp} "
            f"--shard-size {shard_size} "
            f"--shard-number {shard_number} "
            f"--block-number {block_number} "
            f"--storage-backend {storage_backend} "
            f"--output {output_file}'"
        )
        self.log(f"[bench] running: {bench_cmd}")

        def on_out(line):
            self.log(f"[bench] {line}")

        code, out, err = self.ssh.execute(bench_cmd, on_stdout=on_out, timeout=600)
        if code != 0:
            self.log(f"[bench] FAIL: exit={code}")
            if err.strip():
                self.log(f"[bench]   reason: {err.strip()}")
            return None

        code, out, err = self.ssh.execute(
            f"cat {output_file}", timeout=10
        )
        if code != 0 or not out.strip():
            self.log(f"[bench] FAIL: cannot read result file")
            self.log(f"[bench]   reason: {err.strip() if err else 'empty file'}")
            return None

        try:
            result = json.loads(out)
            dump_bw = float(result.get("dump_avg_bw_gbs", 0) or 0)
            load_bw = float(result.get("load_avg_bw_gbs", 0) or 0)
            self.log(f"[bench] OK: dump_avg={dump_bw:.3f} GB/s, "
                     f"load_avg={load_bw:.3f} GB/s")
            return result
        except json.JSONDecodeError as e:
            self.log(f"[bench] FAIL: invalid result JSON - {e}")
            return None

    def _stop_container(self, container_id):
        self.log(f"[container] stopping {container_id} ...")
        code, out, err = self.ssh.execute(f"docker stop {container_id}", timeout=30)
        if code != 0:
            self.log(f"[container] warn: stop returned {code}: {err.strip()}")
        else:
            self.log(f"[container] OK: stopped")

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
        self.log(f"[result] OK: saved to {result_path}")
