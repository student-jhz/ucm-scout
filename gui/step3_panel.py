import tkinter as tk
from tkinter import ttk, messagebox
import os

from gui.widgets import LabeledEntry, ScrollableLogFrame


class Step3Panel(ttk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._build()

    def _build(self):
        config_frame = ttk.LabelFrame(self, text="Input Parameters", padding=10)
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(config_frame, text="Fill in bandwidth and TTFT data, or auto-fill from Step 1 & Step 2 results:",
                  font=("", 9, "italic")).pack(anchor=tk.W, pady=(0, 5))

        row1 = ttk.Frame(config_frame)
        row1.pack(fill=tk.X, pady=2)
        self.bw_entry = LabeledEntry(row1, "Bandwidth (GB/s):", "")
        self.bw_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="From Step1", command=self._auto_fill_bw, width=10).pack(side=tk.LEFT)

        row2 = ttk.Frame(config_frame)
        row2.pack(fill=tk.X, pady=2)
        self.full_ttft_entry = LabeledEntry(row2, "Full Prefill TTFT (ms):", "")
        self.full_ttft_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row2, text="From Step2", command=self._auto_fill_ttft, width=10).pack(side=tk.LEFT)

        row3 = ttk.Frame(config_frame)
        row3.pack(fill=tk.X, pady=2)
        self.hbm_ttft_entry = LabeledEntry(row3, "HBM PC TTFT (ms):", "")
        self.hbm_ttft_entry.pack(side=tk.LEFT, padx=(0, 5))

        row4 = ttk.Frame(config_frame)
        row4.pack(fill=tk.X, pady=2)
        self.output_dir_entry = LabeledEntry(row4, "Output Dir:", "./results/step3")
        self.output_dir_entry.pack(side=tk.LEFT, padx=(0, 5))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        self.analyze_btn = ttk.Button(btn_frame, text="Analyze", command=self._on_analyze)
        self.analyze_btn.pack(side=tk.LEFT, padx=5)

        self.log_frame = ScrollableLogFrame(self, height=8)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        result_frame = ttk.LabelFrame(self, text="Analysis Result", padding=10)
        result_frame.pack(fill=tk.X, padx=5, pady=5)

        self.ttft_range_var = tk.StringVar(value="UCM PC TTFT Range: --")
        ttk.Label(result_frame, textvariable=self.ttft_range_var,
                  font=("Consolas", 11, "bold"), foreground="#d4380d").pack(anchor=tk.W, pady=3)

        self.ttft_avg_var = tk.StringVar(value="Avg TTFT: --")
        ttk.Label(result_frame, textvariable=self.ttft_avg_var,
                  font=("Consolas", 10), foreground="blue").pack(anchor=tk.W, pady=2)

        self.ratio_var = tk.StringVar(value="TTFT Ratio: --")
        ttk.Label(result_frame, textvariable=self.ratio_var,
                  font=("Consolas", 10), foreground="green").pack(anchor=tk.W, pady=2)

    def _auto_fill_bw(self):
        if self.app.step1_panel:
            bw = self.app.step1_panel.get_bandwidth()
            if bw:
                self.bw_entry.set(f"{bw:.2f}")
            else:
                messagebox.showinfo("Info", "No bandwidth result from Step 1. Run Step 1 first or enter manually.")

    def _auto_fill_ttft(self):
        if self.app.step2_panel:
            full_ttft = self.app.step2_panel.get_full_ttft()
            hbm_ttft = self.app.step2_panel.get_hbm_ttft()
            if full_ttft:
                self.full_ttft_entry.set(f"{full_ttft:.2f}")
            if hbm_ttft:
                self.hbm_ttft_entry.set(f"{hbm_ttft:.2f}")
            if not full_ttft and not hbm_ttft:
                messagebox.showinfo("Info", "No TTFT results from Step 2. Run Step 2 first or enter manually.")

    def _on_analyze(self):
        try:
            bw = float(self.bw_entry.get()) if self.bw_entry.get() else 0
            full_ttft = float(self.full_ttft_entry.get()) if self.full_ttft_entry.get() else 0
            hbm_ttft = float(self.hbm_ttft_entry.get()) if self.hbm_ttft_entry.get() else 0
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers")
            return

        self.log_frame.clear()
        from core.analyzer import Analyzer

        def log(msg):
            self.log_frame.append(msg)
            if self.app.log_mgr:
                self.app.log_mgr.log(msg)

        analyzer = Analyzer(log)
        result = analyzer.analyze(
            bandwidth_gbs=bw,
            full_prefill_ttft_ms=full_ttft,
            hbm_pc_ttft_ms=hbm_ttft,
            output_dir=self.output_dir_entry.get() or "./results/step3",
        )

        if result:
            rng = result["ucm_pc_ttft_range_ms"]
            self.ttft_range_var.set(f"UCM PC TTFT Range: [{rng[0]:.2f}, {rng[1]:.2f}] ms")
            self.ttft_avg_var.set(f"Avg UCM PC TTFT: {result['ucm_pc_ttft_avg_ms']:.2f} ms")
            self.ratio_var.set(f"TTFT Ratio (Full/HBM_PC): {result['ttft_ratio']:.2f}x")
            messagebox.showinfo("Analysis Complete",
                                f"UCM PC TTFT Range: [{rng[0]:.2f}, {rng[1]:.2f}] ms\n"
                                f"Avg: {result['ucm_pc_ttft_avg_ms']:.2f} ms")
