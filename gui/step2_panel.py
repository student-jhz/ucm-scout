import tkinter as tk
from tkinter import ttk, messagebox
import threading

from gui.widgets import LabeledEntry, ScrollableLogFrame
from i18n import tr, on_lang_change


class Step2Panel(ttk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._running = False
        self._result_data = None
        self._build()
        on_lang_change(self.refresh_language)

    def _build(self):
        self.config_frame = ttk.LabelFrame(self, text=tr("step2.config"), padding=10)
        self.config_frame.pack(fill=tk.X, padx=5, pady=5)

        self.service_url_entry = LabeledEntry(self.config_frame, tr("step2.service_url"), "http://192.168.1.100:8000")
        self.service_url_entry.pack(fill=tk.X, pady=2)
        self.model_path_entry = LabeledEntry(self.config_frame, tr("step2.model_path"), "/models/llama-7b")
        self.model_path_entry.pack(fill=tk.X, pady=2)
        self.model_name_entry = LabeledEntry(self.config_frame, tr("step2.model_name"), "llama-7b")
        self.model_name_entry.pack(fill=tk.X, pady=2)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        self.run_btn = ttk.Button(btn_frame, text=tr("step2.run"), command=self._on_run)
        self.run_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text=tr("step2.stop"), command=self._on_stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(self, mode="determinate", length=400)
        self.progress.pack(fill=tk.X, padx=5, pady=2)
        self.progress_label = ttk.Label(self, text="0%")
        self.progress_label.pack(anchor=tk.W, padx=5)

        self.log_frame = ScrollableLogFrame(self, height=8)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.result_frame = ttk.LabelFrame(self, text=tr("step2.results"), padding=5)
        self.result_frame.pack(fill=tk.X, padx=5, pady=5)
        self.full_result_var = tk.StringVar(value=tr("step2.full_result_default"))
        ttk.Label(self.result_frame, textvariable=self.full_result_var,
                  font=("Consolas", 10), foreground="blue").pack(anchor=tk.W, pady=2)
        self.hbm_result_var = tk.StringVar(value=tr("step2.hbm_result_default"))
        ttk.Label(self.result_frame, textvariable=self.hbm_result_var,
                  font=("Consolas", 10), foreground="green").pack(anchor=tk.W, pady=2)

        self._result_state = "default"

    def _on_run(self):
        if not self.app.ssh or not self.app.ssh.connected:
            messagebox.showwarning(tr("title.warning"), tr("msg.no_ssh"))
            return
        if not self.service_url_entry.get():
            messagebox.showwarning(tr("title.validation_error"), tr("msg.no_service_url"))
            return
        if not self.model_path_entry.get():
            messagebox.showwarning(tr("title.validation_error"), tr("msg.no_model_path"))
            return
        if not self.model_name_entry.get():
            messagebox.showwarning(tr("title.validation_error"), tr("msg.no_model_name"))
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
        self.log_frame.append(tr("step2.stopped"))
        self.run_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.progress["value"] = 0
        self.progress_label.configure(text="0%")

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
            self._result_data = {
                "full": result.get("full_prefill_ttft_ms", 0),
                "hbm": result.get("hbm_pc_ttft_ms", 0),
            }
            self._result_state = "success"
        else:
            self._result_data = None
            self._result_state = "failed"
        self._format_result()

    def _format_result(self):
        if self._result_state == "success" and self._result_data:
            self.full_result_var.set(tr("step2.full_result", v=self._result_data["full"]))
            self.hbm_result_var.set(tr("step2.hbm_result", v=self._result_data["hbm"]))
        elif self._result_state == "failed":
            self.full_result_var.set(tr("step2.full_failed"))
            self.hbm_result_var.set(tr("step2.hbm_failed"))
        else:
            self.full_result_var.set(tr("step2.full_result_default"))
            self.hbm_result_var.set(tr("step2.hbm_result_default"))

    def refresh_language(self):
        self.config_frame.configure(text=tr("step2.config"))
        self.service_url_entry.set_label(tr("step2.service_url"))
        self.model_path_entry.set_label(tr("step2.model_path"))
        self.model_name_entry.set_label(tr("step2.model_name"))
        self.run_btn.configure(text=tr("step2.run"))
        self.stop_btn.configure(text=tr("step2.stop"))
        self.result_frame.configure(text=tr("step2.results"))
        self._format_result()

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
