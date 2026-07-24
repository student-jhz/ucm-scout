import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os

from gui.widgets import LabeledEntry, ScrollableLogFrame


class Step1Panel(ttk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._running = False
        self._build()

    def _build(self):
        config_frame = ttk.LabelFrame(self, text="Bandwidth Test Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        row1 = ttk.Frame(config_frame)
        row1.pack(fill=tk.X, pady=2)
        self.model_dir_entry = LabeledEntry(row1, "Model Weight Dir:", "/models/llama-7b")
        self.model_dir_entry.pack(side=tk.LEFT, padx=(0, 5))
        btn = ttk.Button(row1, text="Browse...", width=8, command=self._browse_model)
        btn.pack(side=tk.LEFT)

        row2 = ttk.Frame(config_frame)
        row2.pack(fill=tk.X, pady=2)
        self.dp_entry = LabeledEntry(row2, "DP Count:", "1", width=8)
        self.dp_entry.pack(side=tk.LEFT, padx=(0, 20))
        self.tp_entry = LabeledEntry(row2, "TP Count:", "1", width=8)
        self.tp_entry.pack(side=tk.LEFT, padx=(0, 20))

        row3 = ttk.Frame(config_frame)
        row3.pack(fill=tk.X, pady=2)
        self.kv_dir_entry = LabeledEntry(row3, "KV Cache Dir:", "/data/kvcache")
        self.kv_dir_entry.pack(side=tk.LEFT, padx=(0, 5))

        row4 = ttk.Frame(config_frame)
        row4.pack(fill=tk.X, pady=2)
        self.output_dir_entry = LabeledEntry(row4, "Output Dir:", "./results/step1")
        self.output_dir_entry.pack(side=tk.LEFT, padx=(0, 5))
        btn2 = ttk.Button(row4, text="Browse...", width=8, command=self._browse_output)
        btn2.pack(side=tk.LEFT)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        self.run_btn = ttk.Button(btn_frame, text="Execute Bandwidth Test", command=self._on_run)
        self.run_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self._on_stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(self, mode="determinate", length=400)
        self.progress.pack(fill=tk.X, padx=5, pady=2)
        self.progress_label = ttk.Label(self, text="0%")
        self.progress_label.pack(anchor=tk.W, padx=5)

        self.log_frame = ScrollableLogFrame(self, height=10)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        result_frame = ttk.LabelFrame(self, text="Result", padding=5)
        result_frame.pack(fill=tk.X, padx=5, pady=5)
        self.result_var = tk.StringVar(value="--")
        ttk.Label(result_frame, textvariable=self.result_var, font=("Consolas", 10, "bold"), foreground="blue").pack(anchor=tk.W)

    def _browse_model(self):
        path = filedialog.askdirectory(title="Select Model Weight Directory")
        if path:
            self.model_dir_entry.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_dir_entry.set(path)

    def _on_run(self):
        if not self.app.ssh or not self.app.ssh.connected:
            messagebox.showwarning("Warning", "Please connect to remote host first")
            return
        self._running = True
        self.run_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.progress["value"] = 0
        self.progress_label.configure(text="0%")
        self.log_frame.clear()
        self.result_var.set("Running...")

        thread = threading.Thread(target=self._run_test, daemon=True)
        thread.start()

    def _on_stop(self):
        self._running = False
        self.log_frame.append("STOPPED by user")

    def _run_test(self):
        from core.bandwidth_test import BandwidthTestController

        def log(msg):
            self.after(0, lambda: self.log_frame.append(msg))
            if self.app.log_mgr:
                self.app.log_mgr.log(msg)

        def progress(pct, msg):
            self.after(0, lambda: self._update_progress(pct, msg))

        controller = BandwidthTestController(self.app.ssh, log, progress)
        output_dir = self.output_dir_entry.get() or "./results/step1"
        result = controller.run(
            model_weight_dir=self.model_dir_entry.get(),
            dp=int(self.dp_entry.get() or 1),
            tp=int(self.tp_entry.get() or 1),
            kv_cache_dir=self.kv_dir_entry.get(),
            request_len=self.app.scenario_params.get_request_len(),
            concurrency=self.app.scenario_params.get_concurrency(),
            output_dir=output_dir,
        )

        self.after(0, lambda: self._on_finish(result))

    def _update_progress(self, pct, msg):
        self.progress["value"] = pct
        self.progress_label.configure(text=f"{pct}% - {msg}")

    def _on_finish(self, result):
        self._running = False
        self.run_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        if result:
            bw = result.get("bandwidth_gbs", 0)
            self.result_var.set(f"Actual Bandwidth: {bw:.2f} GB/s")
        else:
            self.result_var.set("Test failed or no result")

    def get_bandwidth(self):
        text = self.result_var.get()
        import re
        m = re.search(r"([\d.]+)\s*GB/s", text)
        if m:
            return float(m.group(1))
        return None
