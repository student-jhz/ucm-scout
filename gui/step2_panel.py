import tkinter as tk
from tkinter import ttk, messagebox
import threading

from gui.widgets import LabeledEntry, ScrollableLogFrame


class Step2Panel(ttk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._running = False
        self._build()

    def _build(self):
        config_frame = ttk.LabelFrame(self, text="Online Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        self.service_url_entry = LabeledEntry(config_frame, "Service URL:", "http://192.168.1.100:8000")
        self.service_url_entry.pack(fill=tk.X, pady=2)
        self.model_path_entry = LabeledEntry(config_frame, "Model Path:", "/models/llama-7b")
        self.model_path_entry.pack(fill=tk.X, pady=2)
        self.model_name_entry = LabeledEntry(config_frame, "Model Name:", "llama-7b")
        self.model_name_entry.pack(fill=tk.X, pady=2)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        self.run_btn = ttk.Button(btn_frame, text="Execute TTFT Test", command=self._on_run)
        self.run_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self._on_stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(self, mode="determinate", length=400)
        self.progress.pack(fill=tk.X, padx=5, pady=2)
        self.progress_label = ttk.Label(self, text="0%")
        self.progress_label.pack(anchor=tk.W, padx=5)

        self.log_frame = ScrollableLogFrame(self, height=8)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        result_frame = ttk.LabelFrame(self, text="Results", padding=5)
        result_frame.pack(fill=tk.X, padx=5, pady=5)
        self.full_result_var = tk.StringVar(value="Full Prefill TTFT: -- ms")
        ttk.Label(result_frame, textvariable=self.full_result_var, font=("Consolas", 10), foreground="blue").pack(anchor=tk.W, pady=2)
        self.hbm_result_var = tk.StringVar(value="HBM PC TTFT: -- ms")
        ttk.Label(result_frame, textvariable=self.hbm_result_var, font=("Consolas", 10), foreground="green").pack(anchor=tk.W, pady=2)

    def _on_run(self):
        if not self.app.ssh or not self.app.ssh.connected:
            messagebox.showwarning("Warning", "Please connect to remote host first")
            return
        if not self.service_url_entry.get():
            messagebox.showwarning("Validation Error", "Service URL is required")
            return
        if not self.model_path_entry.get():
            messagebox.showwarning("Validation Error", "Model Path is required")
            return
        if not self.model_name_entry.get():
            messagebox.showwarning("Validation Error", "Model Name is required")
            return
        self._running = True
        self.run_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.progress["value"] = 0
        self.progress_label.configure(text="0%")
        self.log_frame.clear()

        thread = threading.Thread(target=self._run_online_test, daemon=True)
        thread.start()

    def _on_stop(self):
        self._running = False
        self.log_frame.append("STOPPED by user")

    def _run_online_test(self):
        from core.ttft_test import TTFTTestController

        def log(msg):
            self.after(0, lambda: self.log_frame.append(msg))
            if self.app.log_mgr:
                self.app.log_mgr.log(msg)

        def progress(pct, msg):
            self.after(0, lambda: self._update_progress(pct, msg))

        controller = TTFTTestController(log, progress)
        result = controller.run_online(
            service_url=self.service_url_entry.get(),
            model_path=self.model_path_entry.get(),
            model_name=self.model_name_entry.get(),
            request_len=self.app.scenario_params.get_request_len(),
            concurrency=self.app.scenario_params.get_concurrency(),
        )

        if result:
            controller.save_results("./results/step2")
        self.after(0, lambda: self._on_finish(result))

    def _update_progress(self, pct, msg):
        self.progress["value"] = pct
        self.progress_label.configure(text=f"{pct}% - {msg}")

    def _on_finish(self, result):
        self._running = False
        self.run_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.progress["value"] = 0
        self.progress_label.configure(text="0%")
        if result:
            self.full_result_var.set(f"Full Prefill TTFT: {result.get('full_prefill_ttft_ms', 0):.2f} ms")
            self.hbm_result_var.set(f"HBM PC TTFT: {result.get('hbm_pc_ttft_ms', 0):.2f} ms")
        else:
            self.full_result_var.set("Full Prefill TTFT: -- ms (failed)")
            self.hbm_result_var.set("HBM PC TTFT: -- ms (failed)")

    def get_full_ttft(self):
        import re
        m = re.search(r"([\d.]+)\s*ms", self.full_result_var.get())
        if m:
            return float(m.group(1))
        return None

    def get_hbm_ttft(self):
        import re
        m = re.search(r"([\d.]+)\s*ms", self.hbm_result_var.get())
        if m:
            return float(m.group(1))
        return None
