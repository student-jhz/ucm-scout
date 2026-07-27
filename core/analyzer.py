import json
import os
from datetime import datetime


class Analyzer:
    DEFAULT_PCIE_BW_GBS = 50.0

    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda msg: None)
        self.results = {}

    def analyze(
        self,
        load_bw_gbs,
        full_prefill_ttft_ms,
        hbm_pc_ttft_ms,
        shard_size,
        shard_number,
        block_number,
        pcie_bw_gbs=None,
        output_dir=None,
    ):
        if pcie_bw_gbs is None or pcie_bw_gbs <= 0:
            pcie_bw_gbs = self.DEFAULT_PCIE_BW_GBS

        self.log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] analysis started")
        self.log(f"  load_bw: {load_bw_gbs:.3f} GB/s (SSD->DRAM)")
        self.log(f"  pcie_bw: {pcie_bw_gbs:.1f} GB/s (DRAM->HBM)")
        self.log(f"  full_prefill: {full_prefill_ttft_ms:.2f} ms")
        self.log(f"  hbm_pc_hit: {hbm_pc_ttft_ms:.2f} ms")
        self.log(f"  shard_size: {shard_size} B, shard_number: {shard_number}, "
                 f"block_number: {block_number}")

        total_bytes = shard_size * shard_number * block_number
        bytes_per_layer = shard_size * block_number

        self.log(f"  total_kv_bytes: {total_bytes} B ({total_bytes / 1e6:.2f} MB)")

        t_compute_total_ms = hbm_pc_ttft_ms
        t_compute_per_layer_ms = (
            hbm_pc_ttft_ms / shard_number if shard_number > 0 else hbm_pc_ttft_ms
        )

        t_ssd_per_layer_ms = (bytes_per_layer / max(load_bw_gbs * 1e9, 1e-9)) * 1000
        t_hbm_per_layer_ms = (bytes_per_layer / max(pcie_bw_gbs * 1e9, 1e-9)) * 1000

        t_io_per_layer_ms = t_ssd_per_layer_ms + t_hbm_per_layer_ms
        t_io_total_ms = t_io_per_layer_ms * shard_number

        self.log("--- IO Breakdown ---")
        self.log(f"  SSD->DRAM per layer: {t_ssd_per_layer_ms:.3f} ms "
                 f"({bytes_per_layer / 1e6:.2f} MB @ {load_bw_gbs:.1f} GB/s)")
        self.log(f"  DRAM->HBM per layer: {t_hbm_per_layer_ms:.3f} ms "
                 f"(@ {pcie_bw_gbs:.1f} GB/s)")
        self.log(f"  IO per layer total:  {t_io_per_layer_ms:.3f} ms")
        self.log(f"  Compute per layer:   {t_compute_per_layer_ms:.3f} ms")

        if t_io_per_layer_ms <= t_compute_per_layer_ms:
            ucm_ttft_ms = hbm_pc_ttft_ms + t_io_per_layer_ms
            strategy = "pipelined (IO hidden by compute)"
            self.log(f"  [pipeline] IO per layer <= compute per layer "
                     f"({t_io_per_layer_ms:.3f} <= {t_compute_per_layer_ms:.3f})")
            self.log(f"  [pipeline] IO hidden, UCM PC TTFT ≈ HBM PC + first layer load")
        else:
            ucm_ttft_ms = t_io_total_ms + t_compute_per_layer_ms
            strategy = "pipelined (IO bottleneck)"
            self.log(f"  [pipeline] IO per layer > compute per layer "
                     f"({t_io_per_layer_ms:.3f} > {t_compute_per_layer_ms:.3f})")
            self.log(f"  [pipeline] IO bottleneck, TTFT = all IO + last layer compute")

        is_beneficial = ucm_ttft_ms < full_prefill_ttft_ms
        ttft_ratio = full_prefill_ttft_ms / max(ucm_ttft_ms, 0.001) if is_beneficial else 0
        slowdown = ucm_ttft_ms / max(full_prefill_ttft_ms, 0.001) if not is_beneficial else 0
        ratio_vs_hbm = ucm_ttft_ms / max(hbm_pc_ttft_ms, 0.001)

        self.log("--- Result ---")
        self.log(f"  UCM PC TTFT: {ucm_ttft_ms:.2f} ms")
        self.log(f"  Strategy: {strategy}")
        self.log(f"  vs Full Prefill: {'+' if is_beneficial else '-'}"
                 f"{abs(ucm_ttft_ms - full_prefill_ttft_ms):.2f} ms")
        if is_beneficial:
            self.log(f"  Speedup: {ttft_ratio:.2f}x over full prefill")
        else:
            self.log(f"  Slowdown: {slowdown:.2f}x slower than full prefill")
            self.log(f"  WARNING: UCM PC slower than recomputation at this bandwidth!")
        self.log(f"  vs HBM PC: {ratio_vs_hbm:.2f}x slowdown")

        ucm_ttft_lo = hbm_pc_ttft_ms + t_io_per_layer_ms
        ucm_ttft_hi = t_io_total_ms + t_compute_per_layer_ms

        self.results = {
            "timestamp": datetime.now().isoformat(),
            "load_bw_gbs": load_bw_gbs,
            "pcie_bw_gbs": pcie_bw_gbs,
            "full_prefill_ttft_ms": full_prefill_ttft_ms,
            "hbm_pc_ttft_ms": hbm_pc_ttft_ms,
            "shard_size": shard_size,
            "shard_number": shard_number,
            "block_number": block_number,
            "total_kv_bytes": total_bytes,
            "t_ssd_per_layer_ms": t_ssd_per_layer_ms,
            "t_hbm_per_layer_ms": t_hbm_per_layer_ms,
            "t_io_per_layer_ms": t_io_per_layer_ms,
            "t_compute_per_layer_ms": t_compute_per_layer_ms,
            "strategy": strategy,
            "ucm_pc_ttft_ms": ucm_ttft_ms,
            "ucm_pc_ttft_range_ms": [ucm_ttft_lo, ucm_ttft_hi],
            "is_beneficial": is_beneficial,
            "speedup_vs_full": ttft_ratio,
            "slowdown_vs_full": slowdown,
            "ratio_vs_hbm_pc": ratio_vs_hbm,
        }

        if output_dir:
            self.save_results(output_dir)

        return self.results

    def save_results(self, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "analysis_result.json")
        with open(path, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        self.log(f"analysis saved to {path}")
        return path
