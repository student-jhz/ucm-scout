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

        self._build()
        on_lang_change(self.refresh_language)

    def _build(self):
        top_bar = ttk.Frame(self)
        top_bar.pack(fill=tk.X, padx=5, pady=(5, 0))
        self._build_lang_switcher(top_bar)

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
        self.notebook.tab(self.step1_panel, text=tr("step1.tab"))
        self.notebook.tab(self.step2_panel, text=tr("step2.tab"))
        self.notebook.tab(self.step3_panel, text=tr("step3.tab"))
        self.log_frame.configure(text=tr("global_log"))
        self.status_label.configure(text=tr("status.footer"))

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
