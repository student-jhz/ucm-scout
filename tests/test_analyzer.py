import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.analyzer import Analyzer


class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.logs = []

        def log(msg):
            self.logs.append(msg)

        self.analyzer = Analyzer(log_callback=log)

    def test_init(self):
        self.assertEqual(len(self.logs), 0)

    def test_analyze_basic(self):
        result = self.analyzer.analyze(
            load_bw_gbs=5.0,
            full_prefill_ttft_ms=50.0,
            hbm_pc_ttft_ms=10.0,
            shard_size=524288,
            shard_number=32,
            block_number=8,
        )
        self.assertIn("ucm_pc_ttft_ms", result)
        self.assertGreater(result["ucm_pc_ttft_ms"], result["hbm_pc_ttft_ms"])
        self.assertTrue(result["is_beneficial"])
        self.assertGreater(result["speedup_vs_full"], 1.0)

    def test_analyze_slow_bandwidth(self):
        result = self.analyzer.analyze(
            load_bw_gbs=0.1,
            full_prefill_ttft_ms=50.0,
            hbm_pc_ttft_ms=5.0,
            shard_size=524288,
            shard_number=32,
            block_number=16,
        )
        self.assertIn("ucm_pc_ttft_ms", result)
        has_warning = any("slower" in l.lower() for l in self.logs)
        self.assertTrue(has_warning)
        self.assertFalse(result["is_beneficial"])

    def test_analyze_io_hidden(self):
        result = self.analyzer.analyze(
            load_bw_gbs=100.0,
            full_prefill_ttft_ms=50.0,
            hbm_pc_ttft_ms=10.0,
            shard_size=524288,
            shard_number=32,
            block_number=8,
        )
        self.assertIn("IO hidden", result["strategy"])

    def test_analyze_pipeline(self):
        result = self.analyzer.analyze(
            load_bw_gbs=3.0,
            full_prefill_ttft_ms=100.0,
            hbm_pc_ttft_ms=8.0,
            shard_size=524288,
            shard_number=32,
            block_number=8,
        )
        self.assertIsNotNone(result)
        self.assertGreater(result["ratio_vs_hbm_pc"], 1.0)

    def test_save_results(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            self.analyzer.analyze(
                load_bw_gbs=5.0,
                full_prefill_ttft_ms=50.0,
                hbm_pc_ttft_ms=10.0,
                shard_size=524288,
                shard_number=32,
                block_number=8,
                output_dir=tmpdir,
            )
            path = os.path.join(tmpdir, "analysis_result.json")
            self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
