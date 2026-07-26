import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os

from gui.widgets import LabeledEntry, ScrollableLogFrame
from i18n import tr, on_lang_change


class Step1Panel(ttk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._running = False
        self._result_data = None
        self._run_state = "idle"
        self._build()
        on_lang_change(self.refresh_language)

    def _build(self):
        self.config_frame = ttk.LabelFrame(self, text=tr("step1.config"), padding=10)
        self.config_frame.pack(fill=tk.X, padx=5, pady=5)

        row1 = ttk.Frame(self.config_frame)
        row1.pack(fill=tk.X, pady=2)
        self.model_dir_entry = LabeledEntry(row1, tr("step1.model_dir"), "/models/llama-7b")
        self.model_dir_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.browse_model_btn = ttk.Button(row1, text=tr("step1.browse"), width=8, command=self._browse_model)
        self.browse_model_btn.pack(side=tk.LEFT)

        row2 = ttk.Frame(self.config_frame)
        row2.pack(fill=tk.X, pady=2)
        self.dp_entry = LabeledEntry(row2, tr("step1.dp"), "1", width=8)
        self.dp_entry.pack(side=tk.LEFT, padx=(0, 20))
        self.tp_entry = LabeledEntry(row2, tr("step1.tp"), "1", width=8)
        self.tp_entry.pack(side=tk.LEFT, padx=(0, 20))

        row3 = ttk.Frame(self.config_frame)
        row3.pack(fill=tk.X, pady=2)
        self.kv_dir_entry = LabeledEntry(row3, tr("step1.kv_dir"), "/data/kvcache")
        self.kv_dir_entry.pack(side=tk.LEFT, padx=(0, 5))

        row4 = ttk.Frame(self.config_frame)
        row4.pack(fill=tk.X, pady=2)
        self.output_dir_entry = LabeledEntry(row4, tr("step1.output_dir"), "./results/step1")
        self.output_dir_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.browse_output_btn = ttk.Button(row4, text=tr("step1.browse"), width=8, command=self._browse_output)
        self.browse_output_btn.pack(side=tk.LEFT)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        self.run_btn = ttk.Button(btn_frame, text=tr("step1.run"), command=self._on_run)
        self.run_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text=tr("step1.stop"), command=self._on_stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(self, mode="determinate", length=400)
        self.progress.pack(fill=tk.X, padx=5, pady=2)
        self.progress_label = ttk.Label(self, text="0%")
        self.progress_label.pack(anchor=tk.W, padx=5)

        self.log_frame = ScrollableLogFrame(self, height=10)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.result_frame = ttk.LabelFrame(self, text=tr("step1.result"), padding=5)
        self.result_frame.pack(fill=tk.X, padx=5, pady=5)
        self.result_var = tk.StringVar(value=tr("step1.default_result"))
        ttk.Label(self.result_frame, textvariable=self.result_var,
                  font=("Consolas", 10, "bold"), foreground="blue").pack(anchor=tk.W)

    def _browse_model(self):
        path = filedialog.askdirectory(title=tr("step1.browse_model_title"))
        if path:
            self.model_dir_entry.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title=tr("step1.browse_output_title"))
        if path:
            self.output_dir_entry.set(path)

    def _on_run(self):
        if not self.app.ssh or not self.app.ssh.connected:
            messagebox.showwarning(tr("title.warning"), tr("msg.no_ssh"))
            return
        if not self.model_dir_entry.get():
            messagebox.showwarning(tr("title.validation_error"), tr("msg.no_model_dir"))
            return
        self._running = True
        self._run_state = "running"
        self.run_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.progress["value"] = 0
        self.progress_label.configure(text="0%")
        self.log_frame.clear()
        self.result_var.set(tr("step1.running"))

        thread = threading.Thread(target=self._run_test, daemon=True)
        thread.start()

    def _on_stop(self):
        self._running = False
        self.log_frame.append(tr("step1.stopped"))

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
        self.progress["value"] = 0
        self.progress_label.configure(text="0%")
        if result:
            self._result_data = {"bw": result.get("bandwidth_gbs", 0)}
            self._run_state = "success"
            self._format_result()
        else:
            self._result_data = None
            self._run_state = "failed"
            self.result_var.set(tr("step1.failed"))

    def _format_result(self):
        if self._result_data:
            self.result_var.set(tr("step1.bandwidth_result", bw=self._result_data["bw"]))

    def refresh_language(self):
        self.config_frame.configure(text=tr("step1.config"))
        self.model_dir_entry.set_label(tr("step1.model_dir"))
        self.browse_model_btn.configure(text=tr("step1.browse"))
        self.dp_entry.set_label(tr("step1.dp"))
        self.tp_entry.set_label(tr("step1.tp"))
        self.kv_dir_entry.set_label(tr("step1.kv_dir"))
        self.output_dir_entry.set_label(tr("step1.output_dir"))
        self.browse_output_btn.configure(text=tr("step1.browse"))
        self.run_btn.configure(text=tr("step1.run"))
        self.stop_btn.configure(text=tr("step1.stop"))
        self.result_frame.configure(text=tr("step1.result"))
        if self._running:
            pass
        elif self._result_data:
            self._format_result()
        elif self._run_state == "failed":
            self.result_var.set(tr("step1.failed"))
        else:
            self.result_var.set(tr("step1.default_result"))

    def get_bandwidth(self):
        text = self.result_var.get()
        import re
        m = re.search(r"([\d.]+)\s*GB/s", text)
        if m:
            return float(m.group(1))
        return None
