import json
import os
from datetime import datetime


class Analyzer:
    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda msg: None)
        self.results = {}

    def analyze(
        self,
        bandwidth_gbs,
        full_prefill_ttft_ms,
        hbm_pc_ttft_ms,
        model_size_gb=None,
        kt_cache_hit_ratio=None,
        output_dir=None,
    ):
        self.log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] analysis started")
        self.log(f"  bandwidth: {bandwidth_gbs} GB/s")
        self.log(f"  full_prefill_ttft: {full_prefill_ttft_ms} ms")
        self.log(f"  hbm_pc_ttft: {hbm_pc_ttft_ms} ms")

        bw_valid = bandwidth_gbs and bandwidth_gbs > 0
        full_ttft_valid = full_prefill_ttft_ms and full_prefill_ttft_ms > 0
        hbm_ttft_valid = hbm_pc_ttft_ms is not None and hbm_pc_ttft_ms > 0

        if not bw_valid:
            self.log("WARNING: bandwidth data is zero/invalid, using reference estimate")
            bandwidth_gbs = self._estimate_bandwidth_from_ttft(full_prefill_ttft_ms)

        if not full_ttft_valid:
            self.log("WARNING: full prefill TTFT is zero/invalid, cannot analyze accurately")

        if not hbm_ttft_valid:
            self.log("WARNING: HBM PC TTFT not provided, estimating bound")

        ucm_min_ttft = hbm_pc_ttft_ms if hbm_ttft_valid else full_prefill_ttft_ms * 0.1
        ucm_max_ttft = full_prefill_ttft_ms if full_ttft_valid else hbm_pc_ttft_ms * 10
        ucm_avg_ttft = (ucm_min_ttft + ucm_max_ttft) / 2

        self.log("--- Analysis Result ---")
        self.log(f"  UCM PC TTFT range: [{ucm_min_ttft:.2f}, {ucm_max_ttft:.2f}] ms")
        self.log(f"  UCM PC TTFT (avg estimate): {ucm_avg_ttft:.2f} ms")

        ttft_ratio = (full_prefill_ttft_ms / max(hbm_pc_ttft_ms, 0.001)) if full_ttft_valid and hbm_ttft_valid else 0
        if ttft_ratio > 0:
            self.log(f"  TTFT ratio (full/hbm_pc): {ttft_ratio:.2f}x")
            self.log(f"  bandwidth_benefit: ~{ttft_ratio:.1f}x latency reduction with HBM PC")

        self.results = {
            "timestamp": datetime.now().isoformat(),
            "bandwidth_gbs": bandwidth_gbs,
            "full_prefill_ttft_ms": full_prefill_ttft_ms,
            "hbm_pc_ttft_ms": hbm_pc_ttft_ms,
            "ucm_pc_ttft_range_ms": [ucm_min_ttft, ucm_max_ttft],
            "ucm_pc_ttft_avg_ms": ucm_avg_ttft,
            "ttft_ratio": ttft_ratio,
        }

        if output_dir:
            self.save_results(output_dir)

        return self.results

    def _estimate_bandwidth_from_ttft(self, ttft_ms):
        return ttft_ms * 0.05 / 1000 if ttft_ms > 0 else 0

    def save_results(self, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "analysis_result.json")
        with open(path, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        self.log(f"analysis saved to {path}")
        return path
