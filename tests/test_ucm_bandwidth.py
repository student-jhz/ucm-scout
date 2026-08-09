import io
import json
import os
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch, PropertyMock, call

from core.ucm_bandwidth import UcmBandwidthController


class FakeSSH:
    def __init__(self):
        self.connected = True
        self._sftp_files = {}

    def execute(self, cmd, on_stdout=None, on_stderr=None, timeout=600):
        if "command -v nvidia-smi" in cmd:
            return 0, "NVIDIA\n", ""
        if "command -v npu-smi" in cmd:
            return 1, "", ""
        if "ls /dev/davinci" in cmd:
            return 1, "", ""
        if "test -d" in cmd and "EXISTS" in cmd:
            return 0, "EXISTS\n", ""
        if "mkdir -p" in cmd and "ucm_bench_" in cmd:
            return 0, "", ""
        if "mkdir -p" in cmd and "ucm_pkgs" in cmd:
            return 0, "", ""
        if "rm -rf" in cmd and "ucm_src" in cmd:
            return 0, "", ""
        if "tar -xzf" in cmd and "ucm_src" in cmd:
            return 0, "", ""
        if "cat" in cmd and "config.json" in cmd:
            cfg = json.dumps({
                "model_type": "llama",
                "num_hidden_layers": 32,
                "num_attention_heads": 32,
                "num_key_value_heads": 8,
                "head_dim": 128,
                "hidden_size": 4096,
            })
            return 0, cfg, ""
        if "docker run" in cmd and "sleep infinity" in cmd:
            return 0, "abcdef123456\n", ""
        if "docker exec" in cmd and "pip install" in cmd:
            if "wrapt" in cmd:
                return 0, "Successfully installed wrapt-1.17.2\n", ""
            else:
                return 0, "Successfully installed uc-manager-0.6.0\n", ""
        if "sed -i" in cmd and "DOWNLOAD_DEPENDENCE" in cmd:
            self._sed_called = True
            return 0, "", ""
        if "docker exec" in cmd and "ucm_bench.py" in cmd:
            result = {
                "worker_number": 1,
                "shard_size": 288,
                "shard_number": 32,
                "block_number": 8,
                "dump_avg_bw_gbs": 3.2,
                "dump_p99_bw_gbs": 2.8,
                "load_avg_bw_gbs": 4.1,
                "load_p99_bw_gbs": 3.6,
            }
            result_text = json.dumps(result)
            if on_stdout:
                on_stdout(result_text)
            return 0, result_text, ""
        if "cat" in cmd and "ucm_bench_result" in cmd:
            return 0, json.dumps({
                "dump_avg_bw_gbs": 3.2,
                "load_avg_bw_gbs": 4.1,
            }), ""
        if "docker stop" in cmd:
            return 0, "abcdef123456\n", ""
        return 0, "ok\n", ""

    def upload_file(self, local_path, remote_path):
        self._sftp_files[remote_path] = local_path


class TestUcmBandwidthController(unittest.TestCase):
    def setUp(self):
        self.ssh = FakeSSH()
        self.log_msgs = []
        self.progress_updates = []

        def log(msg):
            self.log_msgs.append(msg)

        def progress(pct, msg):
            self.progress_updates.append((pct, msg))

        self.ctrl = UcmBandwidthController(self.ssh, log, progress)

    def _make_ucm_src(self):
        """Create a minimal fake ucm_src directory mimicking the real structure."""
        tmp = tempfile.mkdtemp()
        vendors = ["fmt", "spdlog", "pybind11", "zlib"]
        for d in ["ucm", "ucm/shared", "ucm/shared/vendor"]:
            os.makedirs(os.path.join(tmp, d), exist_ok=True)
        for v in vendors:
            vdir = os.path.join(tmp, "ucm", "shared", "vendor", v)
            os.makedirs(vdir, exist_ok=True)
            with open(os.path.join(vdir, "CMakeLists.txt"), "w") as f:
                f.write(f"# {v} stub\n")
        for fname in ["setup.py", "CMakeLists.txt", "MANIFEST.in", "ucm_patch.pth"]:
            with open(os.path.join(tmp, fname), "w") as f:
                f.write(f"# {fname} stub\n")
        return tmp

    def test_init_defaults(self):
        self.assertEqual(self.ctrl.BLOCK_SIZE, 128)
        self.assertEqual(self.ctrl.ELEM_SIZE, 2)
        self.assertFalse(self.ctrl._stopped)

    def test_log_callback(self):
        self.ctrl.log("test message")
        self.assertIn("test message", self.log_msgs)

    def test_progress_callback(self):
        self.ctrl.progress(50, "half done")
        self.assertIn((50, "half done"), self.progress_updates)

    def test_detect_device_nvidia(self):
        result = self.ctrl._detect_device_type()
        self.assertEqual(result, "nvidia")

    def test_parse_model_config(self):
        result = self.ctrl.parse_model_config("/fake/model")
        self.assertIsNotNone(result)
        shard_size, shard_number = result
        self.assertEqual(shard_number, 32)
        self.assertGreater(shard_size, 0)

    @patch("core.ucm_bandwidth.UCM_SRC_DIR", new_callable=lambda: None)
    def test_upload_ucm_source_missing_dir(self, mock_dir):
        with patch("core.ucm_bandwidth.UCM_SRC_DIR", ""):
            result = self.ctrl._upload_ucm_source()
            self.assertFalse(result)

    def test_upload_ucm_source_and_wrapt(self):
        ucm_dir = self._make_ucm_src()
        try:
            import shutil
            dep_dir = tempfile.mkdtemp()
            dep_whl = os.path.join(dep_dir, "wrapt-1.17.2-cp39-cp39-linux_x86_64.whl")
            with open(dep_whl, "w") as f:
                f.write("fake whl")
            try:
                with patch("core.ucm_bandwidth.UCM_SRC_DIR", ucm_dir):
                    ok = self.ctrl._upload_ucm_source()
                    self.assertTrue(ok, "upload_ucm_source should succeed")

                    ok = self.ctrl._upload_wrapt(dep_whl)
                    self.assertTrue(ok, "upload_wrapt should succeed")

                self.assertIn("/tmp/ucm_pkgs/ucm_src.tar.gz", self.ssh._sftp_files)
                self.assertIn("/tmp/ucm_pkgs/wrapt-1.17.2-cp39-cp39-linux_x86_64.whl", self.ssh._sftp_files)
            finally:
                shutil.rmtree(dep_dir)
        finally:
            import shutil
            shutil.rmtree(ucm_dir)

    def test_install_ucm_source_calls_pip_with_platform(self):
        self.ctrl._install_ucm_source("abcdef", "nvidia", "A2")
        cmds = [m for m in self.log_msgs if "pip install" in m]
        self.assertTrue(any("PLATFORM=cuda" in m for m in cmds),
                        "should set PLATFORM=cuda for NVIDIA device")

    def test_install_ucm_source_ascend_a2(self):
        self.ctrl._install_ucm_source("abcdef", "ascend", "A2")
        cmds = [m for m in self.log_msgs if "pip install" in m]
        self.assertTrue(any("PLATFORM=ascend" in m for m in cmds),
                        "should set PLATFORM=ascend for Ascend A2")

    def test_install_ucm_source_ascend_a3(self):
        self.ctrl._install_ucm_source("abcdef", "ascend", "A3")
        cmds = [m for m in self.log_msgs if "pip install" in m]
        self.assertTrue(any("PLATFORM=ascend-a3" in m for m in cmds),
                        "should set PLATFORM=ascend-a3 for Ascend A3")

    def test_sed_patches_download_dependence(self):
        self.ssh._sed_called = False
        self.ctrl._install_ucm_source("abcdef", "nvidia", "A2")
        self.assertTrue(self.ssh._sed_called,
                        "should call sed to set DOWNLOAD_DEPENDENCE=OFF")

    def test_create_container_nvidia(self):
        cid = self.ctrl._create_container("nvidia/vllm:latest",
                                           "/models/llama", "/data/kv", "nvidia")
        self.assertEqual(cid, "abcdef123456")
        self.assertIn("--gpus all", self.log_msgs[-2])

    def test_create_container_ascend(self):
        self.ssh.execute = MagicMock(return_value=(0, "/dev/davinci0\n/dev/davinci1\n", ""))
        cid = self.ctrl._create_container("ascend/vllm:latest",
                                           "/models/llama", "/data/kv", "ascend")
        self.assertIsNotNone(cid)

    def test_install_wrapt(self):
        dep_whl = os.path.join(tempfile.gettempdir(), "wrapt.whl")
        with open(dep_whl, "w") as f:
            f.write("fake")
        try:
            ok = self.ctrl._install_wrapt("abcdef", dep_whl)
            self.assertTrue(ok)
        finally:
            os.remove(dep_whl)

    def test_upload_bench_script(self):
        import core.ucm_bandwidth
        with patch.object(core.ucm_bandwidth, "REMOTE_SCRIPT_DIR",
                          os.path.join(os.path.dirname(__file__), "..", "remote_scripts")):
            ok = self.ctrl._upload_bench_script()
            self.assertTrue(ok)

    def test_stop_container(self):
        self.ctrl._stop_container("abcdef")
        msgs_joined = "\n".join(self.log_msgs)
        self.assertIn("stopping", msgs_joined.lower())

    def test_cleanup_storage(self):
        self.ctrl._cleanup_storage("/data/kv/ucm_bench_20250101")
        self.assertTrue(any("cleaning up" in m for m in self.log_msgs))

    def test_run_not_connected(self):
        self.ssh.connected = False
        result = self.ctrl.run(
            model_path="/models", docker_image="img",
            dep_whl_local="/tmp/fake.whl",
            storage_backend="/data", request_len=1024, tp=1,
            output_dir="/tmp/out",
        )
        self.assertIsNone(result)
        self.assertIn("SSH not connected", self.log_msgs[-1])


class TestUcmBandwidthFullPipeline(unittest.TestCase):
    """End-to-end test using FakeSSH, exercising the full run() flow."""

    def setUp(self):
        self.tmp_out = tempfile.mkdtemp()
        self._tmp_ucm_src = tempfile.mkdtemp()
        vendors = ["fmt", "spdlog", "pybind11", "zlib"]
        for d in ["ucm", "ucm/shared", "ucm/shared/vendor"]:
            os.makedirs(os.path.join(self._tmp_ucm_src, d), exist_ok=True)
        for v in vendors:
            vdir = os.path.join(self._tmp_ucm_src, "ucm", "shared", "vendor", v)
            os.makedirs(vdir, exist_ok=True)
            with open(os.path.join(vdir, "CMakeLists.txt"), "w") as f:
                f.write(f"# {v} stub\n")
        for fname in ["setup.py", "CMakeLists.txt", "MANIFEST.in", "ucm_patch.pth"]:
            with open(os.path.join(self._tmp_ucm_src, fname), "w") as f:
                f.write(f"# {fname} stub\n")

        self.dep_whl = os.path.join(tempfile.gettempdir(), "test-wrapt.whl")
        with open(self.dep_whl, "w") as f:
            f.write("fake whl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_out, ignore_errors=True)
        shutil.rmtree(self._tmp_ucm_src, ignore_errors=True)
        try:
            os.remove(self.dep_whl)
        except OSError:
            pass

    def test_full_pipeline(self):
        ssh = FakeSSH()
        ctrl = UcmBandwidthController(ssh)

        with patch("core.ucm_bandwidth.UCM_SRC_DIR", self._tmp_ucm_src):
            result = ctrl.run(
                model_path="/models/llama-7b",
                docker_image="nvidia/vllm:latest",
                dep_whl_local=self.dep_whl,
                storage_backend="/data/kv",
                request_len=1024,
                tp=1,
                output_dir=self.tmp_out,
                epochs=1,
            )

        self.assertIsNotNone(result, "run() should return results dict")
        self.assertIn("dump_avg_bw_gbs", result)
        self.assertIn("load_avg_bw_gbs", result)
        self.assertEqual(result["shard_number"], 32)

        result_file = os.path.join(self.tmp_out, "ucm_bandwidth_result.json")
        self.assertTrue(os.path.exists(result_file), "should save result JSON")

    def test_full_pipeline_ascend(self):
        ssh = FakeSSH()
        ssh.execute = MagicMock(wraps=ssh.execute)

        ctrl = UcmBandwidthController(ssh)

        with patch("core.ucm_bandwidth.UCM_SRC_DIR", self._tmp_ucm_src):
            result = ctrl.run(
                model_path="/models/llama-7b",
                docker_image="ascend/vllm:latest",
                dep_whl_local=self.dep_whl,
                storage_backend="/data/kv",
                request_len=1024,
                tp=1,
                output_dir=self.tmp_out,
                epochs=1,
            )

        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
