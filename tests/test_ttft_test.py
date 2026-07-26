import unittest
from unittest.mock import MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ttft_test import TTFTTestController


class TestTTFTTest(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.progresses = []

        def log(msg):
            self.logs.append(msg)

        def progress(pct, msg):
            self.progresses.append((pct, msg))

        self.controller = TTFTTestController(log_callback=log, progress_callback=progress)

    def test_init(self):
        self.assertEqual(len(self.logs), 0)
        self.assertEqual(len(self.progresses), 0)

    def test_progress_callback(self):
        self.controller.progress(50, "half done")
        self.assertEqual(self.progresses[-1], (50, "half done"))

    def test_log_callback(self):
        self.controller.log("test log")
        self.assertIn("test log", self.logs[-1])

    @patch("core.ttft_test.requests.get")
    @patch("core.ttft_test.requests.post")
    def test_run_online_service_unreachable(self, mock_post, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        result = self.controller.run_online(
            service_url="http://badhost:8000",
            model_path="/models/test",
            model_name="test-model",
            request_len=512,
            concurrency=1,
        )
        self.assertIsNone(result)

    @patch("core.ttft_test.requests.get")
    @patch("core.ttft_test.requests.post")
    def test_run_online_success(self, mock_post, mock_get):
        mock_health = MagicMock()
        mock_health.status_code = 200
        mock_get.return_value = mock_health

        warmup_resp = MagicMock()
        warmup_resp.status_code = 200

        def make_resp(**kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.iter_lines.return_value = [
                b'data: {"choices":[{"text":"hello"}]}',
                b"data: [DONE]",
            ]
            return resp

        mock_post.side_effect = lambda *a, **kw: make_resp(**kw)

        result = self.controller.run_online(
            service_url="http://localhost:8000",
            model_path="/models/test",
            model_name="test-model",
            request_len=16,
            concurrency=1,
        )
        self.assertIsNotNone(result)
        self.assertIn("full_prefill_ttft_ms", result)

    def test_save_results(self):
        self.controller.results = {
            "mode": "online",
            "full_prefill_ttft_ms": 100.0,
            "hbm_pc_ttft_ms": 20.0,
        }
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.controller.save_results(tmpdir)
            self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
