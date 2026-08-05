import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os

from gui.widgets import LabeledEntry, ScrollableLogFrame
from i18n import tr, on_lang_change

BLOCK_SIZE = 128


class Step1Panel(ttk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._running = False
        self._result_data = None
        self._run_state = "idle"
        self._shard_size = 0
        self._shard_number = 0
        self._build()
        on_lang_change(self.refresh_language)

    def _build(self):
        self.config_frame = ttk.LabelFrame(self, text=tr("step1.config"), padding=10)
        self.config_frame.pack(fill=tk.X, padx=5, pady=5)

        row0 = ttk.Frame(self.config_frame)
        row0.pack(fill=tk.X, pady=2)
        self.model_dir_entry = LabeledEntry(row0, tr("step1.model_dir"), "/models/llama-7b", width=45, label_width=22)
        self.model_dir_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.browse_model_btn = ttk.Button(row0, text=tr("step1.browse"), width=8,
                                            command=self._browse_model)
        self.browse_model_btn.pack(side=tk.LEFT)
        self.tp_entry = LabeledEntry(row0, tr("step1.tp"), "1", width=6, label_width=13)
        self.tp_entry.pack(side=tk.RIGHT)
        self.model_dir_entry.entry.bind("<FocusOut>", lambda e: self._on_model_change())

        row1 = ttk.Frame(self.config_frame)
        row1.pack(fill=tk.X, pady=2)
        self.docker_label = ttk.Label(row1, text=tr("step1.docker_image"), width=22, anchor=tk.W)
        self.docker_label.pack(side=tk.LEFT, padx=(0, 5))
        self.docker_var = tk.StringVar()
        self.docker_combo = ttk.Combobox(row1, textvariable=self.docker_var, width=45)
        self.docker_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.docker_combo.bind("<KeyRelease>", self._filter_images)
        self._all_images = []
        self.docker_refresh_btn = ttk.Button(row1, text=tr("step1.docker_refresh"),
                                              command=self._refresh_images, width=8)
        self.docker_refresh_btn.pack(side=tk.LEFT)

        row2 = ttk.Frame(self.config_frame)
        row2.pack(fill=tk.X, pady=2)
        self.ucm_pkg_entry = LabeledEntry(row2, tr("step1.ucm_pkg"), "", width=45, label_width=22)
        self.ucm_pkg_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.browse_pkg_btn = ttk.Button(row2, text=tr("step1.browse"), width=8,
                                          command=self._browse_pkg)
        self.browse_pkg_btn.pack(side=tk.LEFT)

        row3 = ttk.Frame(self.config_frame)
        row3.pack(fill=tk.X, pady=2)
        self.ucm_dep_entry = LabeledEntry(row3, tr("step1.ucm_dep"), "", width=45, label_width=22)
        self.ucm_dep_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.browse_dep_btn = ttk.Button(row3, text=tr("step1.browse"), width=8,
                                          command=self._browse_dep)
        self.browse_dep_btn.pack(side=tk.LEFT)

        row4 = ttk.Frame(self.config_frame)
        row4.pack(fill=tk.X, pady=2)
        self.storage_entry = LabeledEntry(row4, tr("step1.storage_backend"), "/data/kvcache", width=45, label_width=22)
        self.storage_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.browse_storage_btn = ttk.Button(row4, text=tr("step1.browse"), width=8,
                                              command=self._browse_storage)
        self.browse_storage_btn.pack(side=tk.LEFT)

        row5 = ttk.Frame(self.config_frame)
        row5.pack(fill=tk.X, pady=2)
        self.output_dir_entry = LabeledEntry(row5, tr("step1.output_dir"), "./results/step1", width=45, label_width=22)
        self.output_dir_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.browse_output_btn = ttk.Button(row5, text=tr("step1.browse"), width=8,
                                             command=self._browse_output)
        self.browse_output_btn.pack(side=tk.LEFT)

        self.shard_info_var = tk.StringVar(value="")
        self.shard_info_label = ttk.Label(self.config_frame, textvariable=self.shard_info_var,
                                           font=("", 9, "italic"), foreground="gray")
        self.shard_info_label.pack(anchor=tk.W, pady=(5, 0))

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
        if not self.app.ssh or not self.app.ssh.connected:
            messagebox.showwarning(tr("title.warning"), tr("msg.no_ssh"))
            return
        from gui.widgets import RemoteDirBrowser
        browser = RemoteDirBrowser(self, self.app.ssh,
                                    title=tr("step1.browse_model_title"))
        path = browser.show()
        if path:
            self.model_dir_entry.set(path)
            self._on_model_change()

    def _browse_storage(self):
        if not self.app.ssh or not self.app.ssh.connected:
            messagebox.showwarning(tr("title.warning"), tr("msg.no_ssh"))
            return
        from gui.widgets import RemoteDirBrowser
        browser = RemoteDirBrowser(self, self.app.ssh,
                                    title=tr("step1.storage_backend"))
        path = browser.show()
        if path:
            self.storage_entry.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title=tr("step1.browse_output_title"))
        if path:
            self.output_dir_entry.set(path)

    def _browse_pkg(self):
        path = filedialog.askopenfilename(
            title=tr("step1.browse_pkg_title"),
            filetypes=[("Tar Gzip", "*.tar.gz"), ("All Files", "*.*")])
        if path:
            self.ucm_pkg_entry.set(path)

    def _browse_dep(self):
        path = filedialog.askopenfilename(
            title=tr("step1.browse_dep_title"),
            filetypes=[("Wheel", "*.whl"), ("All Files", "*.*")])
        if path:
            self.ucm_dep_entry.set(path)

    def _refresh_images(self):
        if not self.app.ssh or not self.app.ssh.connected:
            messagebox.showinfo(tr("title.info"), tr("msg.docker_refresh_hint"))
            return
        from core.ucm_bandwidth import UcmBandwidthController
        ctrl = UcmBandwidthController(self.app.ssh)
        images = ctrl.get_docker_images()
        if images:
            self._all_images = sorted(images)
            self.docker_combo["values"] = self._all_images
            self.docker_var.set(self._all_images[0] if self._all_images else "")
            self._log(f"[docker] found {len(images)} image(s)")
        else:
            messagebox.showinfo(tr("title.info"),
                                "No vllm images found. Try a different filter.")

    def _filter_images(self, event):
        text = self.docker_var.get()
        if not self._all_images:
            return
        if not text:
            self.docker_combo["values"] = self._all_images
            return
        filtered = [img for img in self._all_images if text.lower() in img.lower()]
        self.docker_combo["values"] = filtered

    def _on_model_change(self):
        model_path = self.model_dir_entry.get()
        if not model_path or not self.app.ssh or not self.app.ssh.connected:
            return
        from core.ucm_bandwidth import UcmBandwidthController
        ctrl = UcmBandwidthController(self.app.ssh)
        cfg = ctrl.parse_model_config(model_path)
        if cfg:
            self._shard_size, self._shard_number = cfg
        else:
            self._shard_size, self._shard_number = 0, 0
        self._update_shard_info()

    def _update_shard_info(self):
        req_len = self.app.scenario_params.get_request_len()
        blocks = max(1, req_len // BLOCK_SIZE)
        if self._shard_size > 0:
            self.shard_info_var.set(tr("step1.shard_info",
                size=self._shard_size,
                size_kb=self._shard_size / 1024,
                num=self._shard_number,
                blocks=blocks))
        else:
            self.shard_info_var.set("shard: (config.json not parsed) | blocks: " + str(blocks))

    def _on_run(self):
        if not self.app.ssh or not self.app.ssh.connected:
            messagebox.showwarning(tr("title.warning"), tr("msg.no_ssh"))
            return
        if not self.model_dir_entry.get():
            messagebox.showwarning(tr("title.validation_error"), tr("msg.no_model_dir"))
            return
        if not self.docker_var.get():
            messagebox.showwarning(tr("title.validation_error"), tr("msg.no_docker_image"))
            return
        if not self.ucm_pkg_entry.get():
            messagebox.showwarning(tr("title.validation_error"), tr("msg.no_ucm_pkg"))
            return
        if not self.ucm_dep_entry.get():
            messagebox.showwarning(tr("title.validation_error"), tr("msg.no_ucm_dep"))
            return
        if not self.storage_entry.get():
            messagebox.showwarning(tr("title.validation_error"), tr("msg.no_storage_backend"))
            return
        storage_path = self.storage_entry.get()
        ok = messagebox.askyesno(
            tr("title.warning"),
            tr("msg.storage_confirm", path=storage_path),
        )
        if not ok:
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
        self.run_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.progress["value"] = 0
        self.progress_label.configure(text="0%")

    def _run_test(self):
        from core.ucm_bandwidth import UcmBandwidthController

        def log(msg):
            self.after(0, lambda: self.log_frame.append(msg))
            if self.app.log_mgr:
                self.app.log_mgr.log(msg)

        def progress(pct, msg):
            self.after(0, lambda: self._update_progress(pct, msg))

        controller = UcmBandwidthController(self.app.ssh, log, progress)
        result = controller.run(
            model_path=self.model_dir_entry.get(),
            docker_image=self.docker_var.get(),
            ucm_pkg_local=self.ucm_pkg_entry.get(),
            dep_whl_local=self.ucm_dep_entry.get(),
            storage_backend=self.storage_entry.get(),
            request_len=self.app.scenario_params.get_request_len(),
            tp=int(self.tp_entry.get() or 1),
            output_dir=self.output_dir_entry.get() or "./results/step1",
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
            self._result_data = {
                "dump_bw": result.get("dump_avg_bw_gbs", 0),
                "load_bw": result.get("load_avg_bw_gbs", 0),
            }
            self._run_state = "success"
            self._format_result()
        else:
            self._result_data = None
            self._run_state = "failed"
            self.result_var.set(tr("step1.failed"))

    def _format_result(self):
        if self._result_data:
            d = self._result_data
            text = tr("step1.dump_bw", v=d["dump_bw"]) + " | " + tr("step1.load_bw", v=d["load_bw"])
            self.result_var.set(text)

    def _log(self, msg):
        self.log_frame.append(msg)
        if self.app.log_mgr:
            self.app.log_mgr.log(msg)

    def refresh_language(self):
        self.config_frame.configure(text=tr("step1.config"))
        self.model_dir_entry.set_label(tr("step1.model_dir"))
        self.browse_model_btn.configure(text=tr("step1.browse"))
        self.tp_entry.set_label(tr("step1.tp"))
        self.docker_label.configure(text=tr("step1.docker_image"))
        self.docker_refresh_btn.configure(text=tr("step1.docker_refresh"))
        self.ucm_pkg_entry.set_label(tr("step1.ucm_pkg"))
        self.browse_pkg_btn.configure(text=tr("step1.browse"))
        self.ucm_dep_entry.set_label(tr("step1.ucm_dep"))
        self.browse_dep_btn.configure(text=tr("step1.browse"))
        self.storage_entry.set_label(tr("step1.storage_backend"))
        self.browse_storage_btn.configure(text=tr("step1.browse"))
        self.output_dir_entry.set_label(tr("step1.output_dir"))
        self.browse_output_btn.configure(text=tr("step1.browse"))
        self.run_btn.configure(text=tr("step1.run"))
        self.stop_btn.configure(text=tr("step1.stop"))
        self.result_frame.configure(text=tr("step1.result"))
        self._update_shard_info()
        if self._running:
            pass
        elif self._result_data:
            self._format_result()
        elif self._run_state == "failed":
            self.result_var.set(tr("step1.failed"))
        else:
            self.result_var.set(tr("step1.default_result"))

    def get_bandwidth(self):
        if self._result_data:
            return self._result_data.get("load_bw")
        text = self.result_var.get()
        import re
        m = re.search(r"([\d.]+)\s*GB/s", text)
        if m:
            return float(m.group(1))
        return None

    def get_shard_size(self):
        return self._shard_size

    def get_shard_number(self):
        return self._shard_number

    def get_block_number(self):
        return max(1, self.app.scenario_params.get_request_len() // BLOCK_SIZE)
