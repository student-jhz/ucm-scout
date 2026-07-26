import tkinter as tk
from tkinter import ttk, messagebox
import threading

from core.ssh_client import SSHClient
from core.logger import LogManager
from gui.widgets import SSHConnectionPanel, ScenarioParamsPanel, ScrollableLogFrame
from gui.step1_panel import Step1Panel
from gui.step2_panel import Step2Panel
from gui.step3_panel import Step3Panel


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("UCM-Scout - Bandwidth & TTFT Analysis")
        self.geometry("900x850")
        self.minsize(800, 700)

        self.ssh = None
        self.log_mgr = LogManager()
        self.step1_panel = None
        self.step2_panel = None
        self.step3_panel = None

        self._build()

    def _build(self):
        self.ssh_panel = SSHConnectionPanel(self, on_connect=self._handle_ssh)
        self.ssh_panel.pack(fill=tk.X, padx=5, pady=(5, 0))

        self.scenario_params = ScenarioParamsPanel(self)
        self.scenario_params.pack(fill=tk.X, padx=5, pady=5)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.step1_panel = Step1Panel(notebook, self)
        notebook.add(self.step1_panel, text="Step 1: Bandwidth Test")

        self.step2_panel = Step2Panel(notebook, self)
        notebook.add(self.step2_panel, text="Step 2: TTFT Test")

        self.step3_panel = Step3Panel(notebook, self)
        notebook.add(self.step3_panel, text="Step 3: Analysis")

        log_frame = ttk.LabelFrame(self, text="Global Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.global_log = ScrollableLogFrame(log_frame, height=6)
        self.global_log.pack(fill=tk.BOTH, expand=True)

        status = ttk.Label(self, text="Logs saved to ./logs/ | Results saved to ./results/",
                           font=("", 8), foreground="gray")
        status.pack(anchor=tk.W, padx=5, pady=(0, 3))

    def _handle_ssh(self, disconnect=False):
        if disconnect:
            if self.ssh:
                try:
                    self.ssh.disconnect()
                except Exception:
                    pass
                self.ssh = None
            self.ssh_panel.set_connected(False)
            self._log("SSH disconnected")
            return

        vals = self.ssh_panel.get_values()
        if not vals["host"]:
            messagebox.showwarning("Validation Error", "Host is required")
            return
        if not vals["password"]:
            messagebox.showwarning("Validation Error", "Password is required")
            return
        self._log(f"connecting to {vals['host']}:{vals['port']} as {vals['username']}...")
        self.ssh_panel.set_connecting()

        def _connect():
            client = SSHClient(vals["host"], vals["port"], vals["username"], vals["password"])
            try:
                client.connect(timeout=10)
                ok, info = client.test_connection()
                if ok:
                    self.ssh = client
                    self.after(0, lambda: self.ssh_panel.set_connected(True))
                    self._log(f"connected: {info}")
                else:
                    self._log(f"connection test failed: {info}")
                    self.after(0, lambda: self.ssh_panel.set_connected(False))
                    messagebox.showerror("Connection Error", f"Test failed: {info}")
            except Exception as e:
                self._log(f"SSH error: {e}")
                self.after(0, lambda: self.ssh_panel.set_connected(False))
                messagebox.showerror("Connection Error", str(e))

        threading.Thread(target=_connect, daemon=True).start()

    def _log(self, msg):
        self.global_log.append(msg)
        if self.log_mgr:
            self.log_mgr.log(msg)
