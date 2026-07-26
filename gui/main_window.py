import tkinter as tk
from tkinter import ttk, messagebox
import threading

from core.ssh_client import SSHClient
from core.logger import LogManager
from gui.widgets import SSHConnectionPanel, ScenarioParamsPanel, ScrollableLogFrame
from gui.step1_panel import Step1Panel
from gui.step2_panel import Step2Panel
from gui.step3_panel import Step3Panel
from i18n import tr, set_lang, get_lang, on_lang_change


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(tr("app.title"))
        self.geometry("900x850")
        self.minsize(800, 700)

        self.ssh = None
        self.log_mgr = LogManager()
        self.step1_panel = None
        self.step2_panel = None
        self.step3_panel = None
        self._demo_mode = False

        self._build()
        on_lang_change(self.refresh_language)

    def _build(self):
        top_bar = ttk.Frame(self)
        top_bar.pack(fill=tk.X, padx=5, pady=(5, 0))
        self._build_lang_switcher(top_bar)

        self._demo_var = tk.BooleanVar(value=False)
        self._demo_cb = ttk.Checkbutton(top_bar, text=tr("demo.mode"),
                                         variable=self._demo_var, command=self._on_demo_toggle)
        self._demo_cb.pack(side=tk.RIGHT, padx=5)

        self.ssh_panel = SSHConnectionPanel(self, on_connect=self._handle_ssh)
        self.ssh_panel.pack(fill=tk.X, padx=5, pady=(5, 0))

        self.scenario_params = ScenarioParamsPanel(self)
        self.scenario_params.pack(fill=tk.X, padx=5, pady=5)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.step1_panel = Step1Panel(self.notebook, self)
        self.notebook.add(self.step1_panel, text=tr("step1.tab"))

        self.step2_panel = Step2Panel(self.notebook, self)
        self.notebook.add(self.step2_panel, text=tr("step2.tab"))

        self.step3_panel = Step3Panel(self.notebook, self)
        self.notebook.add(self.step3_panel, text=tr("step3.tab"))

        self.log_frame = ttk.LabelFrame(self, text=tr("global_log"), padding=5)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.global_log = ScrollableLogFrame(self.log_frame, height=6)
        self.global_log.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(self, text=tr("status.footer"),
                                       font=("", 8), foreground="gray")
        self.status_label.pack(anchor=tk.W, padx=5, pady=(0, 3))

    def _build_lang_switcher(self, parent):
        ttk.Label(parent, text=tr("lang.label")).pack(side=tk.LEFT, padx=(0, 5))
        self.lang_var = tk.StringVar(value=get_lang())
        self.lang_combo = ttk.Combobox(parent, textvariable=self.lang_var,
                                        values=["en", "zh"], state="readonly", width=6)
        self.lang_combo.pack(side=tk.LEFT)
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_lang_change)

    def _on_lang_change(self, event):
        set_lang(self.lang_var.get())

    def refresh_language(self):
        self.title(tr("app.title"))
        self._demo_cb.configure(text=tr("demo.mode"))
        self.notebook.tab(self.step1_panel, text=tr("step1.tab"))
        self.notebook.tab(self.step2_panel, text=tr("step2.tab"))
        self.notebook.tab(self.step3_panel, text=tr("step3.tab"))
        self.log_frame.configure(text=tr("global_log"))
        self.status_label.configure(text=tr("status.footer"))

    def _on_demo_toggle(self):
        from core.demo import start_demo, stop_demo

        if self._demo_var.get():
            if self.ssh and self.ssh.connected:
                self._handle_ssh(disconnect=True)
            try:
                start_demo()
                self._demo_mode = True
                self._log(f"[Demo] {tr('demo.mode')} ON - {tr('demo.local')}")
                self.ssh_panel.host_entry.set(tr("demo.host"))
                self.ssh_panel.port_entry.set(tr("demo.port"))
                self.ssh_panel.user_entry.set(tr("demo.user"))
                self.ssh_panel.pwd_entry.set(tr("demo.pwd"))
                self.step2_panel.service_url_entry.set(tr("demo.service_url"))
                self.step1_panel.ucm_pkg_entry.set("./demo-package.tar.gz")
                self.step1_panel.ucm_dep_entry.set("./wrapt-demo.whl")
                self.step1_panel.storage_entry.set("/tmp/demo_kvcache")
            except Exception as e:
                self._log(f"[Demo] start failed: {e}")
                self._demo_var.set(False)
                self._demo_mode = False
        else:
            self._demo_mode = False
            stop_demo()
            if self.ssh:
                self._handle_ssh(disconnect=True)
            self._log(f"[Demo] {tr('demo.mode')} OFF")

    def _handle_ssh(self, disconnect=False):
        if disconnect:
            if self.ssh:
                try:
                    self.ssh.disconnect()
                except Exception:
                    pass
                self.ssh = None
            self.ssh_panel.set_connected(False)
            self._log(tr("msg.ssh_disconnected"))
            return

        vals = self.ssh_panel.get_values()
        if not vals["host"]:
            messagebox.showwarning(tr("title.warning"), tr("msg.host_required"))
            return
        if not vals["username"]:
            messagebox.showwarning(tr("title.warning"), tr("msg.user_required"))
            return
        if not vals["password"]:
            messagebox.showwarning(tr("title.warning"), tr("msg.pwd_required"))
            return
        self._log(tr("msg.connecting", host=vals["host"], port=vals["port"], user=vals["username"]))
        self.ssh_panel.set_connecting()

        def _connect():
            if self._demo_mode:
                from core.demo import MockSSHClient
                client = MockSSHClient(vals["host"], vals["port"], vals["username"], vals["password"])
            else:
                client = SSHClient(vals["host"], vals["port"], vals["username"], vals["password"])

            try:
                client.connect(timeout=10)
                ok, info = client.test_connection()
                if ok:
                    self.ssh = client
                    self.after(0, lambda: self.ssh_panel.set_connected(True))
                    self._log(tr("msg.connected", info=info))
                else:
                    self._log(tr("msg.connect_failed", info=info))
                    self.after(0, lambda: self.ssh_panel.set_connected(False))
                    messagebox.showerror(tr("title.connection_error"), tr("msg.connect_failed", info=info))
            except Exception as e:
                self._log(tr("msg.ssh_error", e=e))
                self.after(0, lambda: self.ssh_panel.set_connected(False))
                messagebox.showerror(tr("title.connection_error"), str(e))

        threading.Thread(target=_connect, daemon=True).start()

    def _log(self, msg):
        self.global_log.append(msg)
        if self.log_mgr:
            self.log_mgr.log(msg)
