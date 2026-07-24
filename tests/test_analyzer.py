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
            bandwidth_gbs=100.0,
            full_prefill_ttft_ms=50.0,
            hbm_pc_ttft_ms=10.0,
        )
        self.assertIn("ucm_pc_ttft_range_ms", result)
        self.assertAlmostEqual(result["ucm_pc_ttft_avg_ms"], 30.0)
        self.assertAlmostEqual(result["ttft_ratio"], 5.0)

    def test_analyze_zero_bandwidth(self):
        result = self.analyzer.analyze(
            bandwidth_gbs=0,
            full_prefill_ttft_ms=50.0,
            hbm_pc_ttft_ms=10.0,
        )
        has_warning = any("WARNING" in l for l in self.logs)
        self.assertTrue(has_warning)
        self.assertGreater(result["bandwidth_gbs"], 0)

    def test_analyze_zero_full_ttft(self):
        result = self.analyzer.analyze(
            bandwidth_gbs=100.0,
            full_prefill_ttft_ms=0,
            hbm_pc_ttft_ms=10.0,
        )
        has_warning = any("WARNING" in l for l in self.logs)
        self.assertTrue(has_warning)
        self.assertEqual(result["ttft_ratio"], 0)

    def test_analyze_zero_hbm_ttft(self):
        result = self.analyzer.analyze(
            bandwidth_gbs=100.0,
            full_prefill_ttft_ms=50.0,
            hbm_pc_ttft_ms=0,
        )
        self.assertIsNotNone(result)
        self.assertGreater(result["ucm_pc_ttft_avg_ms"], 0)

    def test_save_results(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            self.analyzer.analyze(
                bandwidth_gbs=100.0,
                full_prefill_ttft_ms=50.0,
                hbm_pc_ttft_ms=10.0,
                output_dir=tmpdir,
            )
            path = os.path.join(tmpdir, "analysis_result.json")
            self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
