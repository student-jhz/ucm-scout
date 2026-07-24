import unittest
from unittest.mock import MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.bandwidth_test import BandwidthTestController


class TestBandwidthTest(unittest.TestCase):
    def setUp(self):
        self.mock_ssh = MagicMock()
        self.logs = []
        self.progresses = []

        def log(msg):
            self.logs.append(msg)

        def progress(pct, msg):
            self.progresses.append((pct, msg))

        self.controller = BandwidthTestController(
            self.mock_ssh, log_callback=log, progress_callback=progress
        )

    def test_init(self):
        self.assertEqual(len(self.logs), 0)
        self.assertEqual(len(self.progresses), 0)

    def test_run_not_connected(self):
        self.mock_ssh.connected = False
        result = self.controller.run(
            model_weight_dir="/models/test",
            dp=1, tp=1,
            kv_cache_dir="/tmp/kv",
            request_len=512,
            concurrency=1,
            output_dir="./results/test",
        )
        self.assertIsNone(result)
        has_error = any("ERROR" in l for l in self.logs)
        self.assertTrue(has_error)

    def test_progress_callback(self):
        self.controller.progress(50, "half done")
        self.assertEqual(self.progresses[-1], (50, "half done"))

    def test_log_callback(self):
        self.controller.log("test message")
        self.assertIn("test message", self.logs[-1])

    def test_generate_bench_script(self):
        script = BandwidthTestController._generate_bench_script()
        self.assertIn("import argparse", script)
        self.assertIn("bandwidth_gbs", script)
        self.assertIn("requests", script)


if __name__ == "__main__":
    unittest.main()
