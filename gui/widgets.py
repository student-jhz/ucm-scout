import tkinter as tk
from tkinter import ttk

from i18n import tr, on_lang_change


class ScrollableLogFrame(ttk.Frame):
    def __init__(self, parent, height=12, **kwargs):
        super().__init__(parent, **kwargs)
        self.text = tk.Text(self, height=height, wrap=tk.WORD, state=tk.DISABLED,
                            font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
                            insertbackground="white")
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def append(self, msg):
        self.text.configure(state=tk.NORMAL)
        self.text.insert(tk.END, msg + "\n")
        self.text.see(tk.END)
        self.text.configure(state=tk.DISABLED)

    def clear(self):
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.configure(state=tk.DISABLED)


class LabeledEntry(ttk.Frame):
    def __init__(self, parent, label, default="", width=30, label_width=12, **kwargs):
        super().__init__(parent, **kwargs)
        self.label_widget = ttk.Label(self, text=label, width=label_width, anchor=tk.W)
        self.label_widget.pack(side=tk.LEFT, padx=(0, 5))
        self.var = tk.StringVar(value=default)
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(str(value))

    def set_label(self, text):
        self.label_widget.configure(text=text)


class SSHConnectionPanel(ttk.LabelFrame):
    def __init__(self, parent, on_connect=None, **kwargs):
        super().__init__(parent, text=tr("ssh.panel"), padding=10, **kwargs)
        self.on_connect = on_connect
        self._state = "disconnected"
        self._build()
        on_lang_change(self.refresh_language)

    def _build(self):
        row1 = ttk.Frame(self)
        row1.pack(fill=tk.X)
        self.host_entry = LabeledEntry(row1, tr("ssh.host"), "192.168.1.100", width=22, label_width=5)
        self.host_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.port_entry = LabeledEntry(row1, tr("ssh.port"), "22", width=8, label_width=5)
        self.port_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.user_entry = LabeledEntry(row1, tr("ssh.user"), "root", width=12, label_width=5)
        self.user_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.pwd_entry = LabeledEntry(row1, tr("ssh.pwd"), "", width=18, label_width=4)
        self.pwd_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.pwd_entry.entry.configure(show="*")

        row2 = ttk.Frame(self)
        row2.pack(fill=tk.X, pady=(5, 0))
        self.status_label = ttk.Label(row2, text=tr("ssh.disconnected"), foreground="gray")
        self.status_label.pack(side=tk.LEFT, padx=5)
        self.connect_btn = ttk.Button(row2, text=tr("ssh.connect"), command=self._on_connect_click)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        self.disconnect_btn = ttk.Button(row2, text=tr("ssh.disconnect"), command=self._on_disconnect_click, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)

    def _on_connect_click(self):
        if self.on_connect:
            self.on_connect()

    def _on_disconnect_click(self):
        if self.on_connect:
            self.on_connect(disconnect=True)

    def _update_state_text(self):
        if self._state == "connected":
            self.status_label.configure(text=tr("ssh.connected"), foreground="green")
            self.connect_btn.configure(state=tk.DISABLED)
            self.disconnect_btn.configure(state=tk.NORMAL)
        elif self._state == "connecting":
            self.status_label.configure(text=tr("ssh.connecting"), foreground="orange")
            self.connect_btn.configure(state=tk.DISABLED)
            self.disconnect_btn.configure(state=tk.DISABLED)
        else:
            self.status_label.configure(text=tr("ssh.disconnected"), foreground="gray")
            self.connect_btn.configure(state=tk.NORMAL)
            self.disconnect_btn.configure(state=tk.DISABLED)

    def set_connecting(self):
        self._state = "connecting"
        self._update_state_text()

    def set_connected(self, connected):
        self._state = "connected" if connected else "disconnected"
        self._update_state_text()

    def refresh_language(self):
        self.configure(text=tr("ssh.panel"))
        self.host_entry.set_label(tr("ssh.host"))
        self.port_entry.set_label(tr("ssh.port"))
        self.user_entry.set_label(tr("ssh.user"))
        self.pwd_entry.set_label(tr("ssh.pwd"))
        self.connect_btn.configure(text=tr("ssh.connect"))
        self.disconnect_btn.configure(text=tr("ssh.disconnect"))
        self._update_state_text()

    def get_values(self):
        return {
            "host": self.host_entry.get(),
            "port": int(self.port_entry.get()) if self.port_entry.get().isdigit() else 22,
            "username": self.user_entry.get(),
            "password": self.pwd_entry.get(),
        }


class ScenarioParamsPanel(ttk.LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text=tr("scenario.panel"), padding=10, **kwargs)
        self._build()
        on_lang_change(self.refresh_language)

    def _build(self):
        row = ttk.Frame(self)
        row.pack(fill=tk.X)
        self.request_len_entry = LabeledEntry(row, tr("scenario.request_len"), "1024", width=12, label_width=16)
        self.request_len_entry.pack(side=tk.LEFT, padx=(0, 20))
        self.concurrency_entry = LabeledEntry(row, tr("scenario.concurrency"), "1", width=12, label_width=14)
        self.concurrency_entry.pack(side=tk.LEFT, padx=(0, 20))

    def refresh_language(self):
        self.configure(text=tr("scenario.panel"))
        self.request_len_entry.set_label(tr("scenario.request_len"))
        self.concurrency_entry.set_label(tr("scenario.concurrency"))

    def get_request_len(self):
        try:
            return int(self.request_len_entry.get())
        except ValueError:
            return 1024

    def get_concurrency(self):
        try:
            return int(self.concurrency_entry.get())
        except ValueError:
            return 1
