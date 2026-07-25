import tkinter as tk
from tkinter import ttk


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
    def __init__(self, parent, label, default="", width=30, **kwargs):
        super().__init__(parent, **kwargs)
        ttk.Label(self, text=label, width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        self.var = tk.StringVar(value=default)
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(str(value))


class SSHConnectionPanel(ttk.LabelFrame):
    def __init__(self, parent, on_connect=None, **kwargs):
        super().__init__(parent, text="SSH Connection", padding=10, **kwargs)
        self.on_connect = on_connect
        self._build()

    def _build(self):
        row1 = ttk.Frame(self)
        row1.pack(fill=tk.X)
        self.host_entry = LabeledEntry(row1, "Host:", "192.168.1.100")
        self.host_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.port_entry = LabeledEntry(row1, "Port:", "22", width=8)
        self.port_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.user_entry = LabeledEntry(row1, "User:", "root")
        self.user_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.pwd_entry = LabeledEntry(row1, "Password:", "", width=20)
        self.pwd_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.pwd_entry.entry.configure(show="*")

        row2 = ttk.Frame(self)
        row2.pack(fill=tk.X, pady=(5, 0))
        self.status_label = ttk.Label(row2, text="disconnected", foreground="gray")
        self.status_label.pack(side=tk.LEFT, padx=5)
        self.connect_btn = ttk.Button(row2, text="Connect", command=self._on_connect_click)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        self.disconnect_btn = ttk.Button(row2, text="Disconnect", command=self._on_disconnect_click, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)

    def _on_connect_click(self):
        if self.on_connect:
            self.on_connect()

    def _on_disconnect_click(self):
        if self.on_connect:
            self.on_connect(disconnect=True)

    def set_connected(self, connected):
        if connected:
            self.status_label.configure(text="connected", foreground="green")
            self.connect_btn.configure(state=tk.DISABLED)
            self.disconnect_btn.configure(state=tk.NORMAL)
        else:
            self.status_label.configure(text="disconnected", foreground="gray")
            self.connect_btn.configure(state=tk.NORMAL)
            self.disconnect_btn.configure(state=tk.DISABLED)

    def get_values(self):
        return {
            "host": self.host_entry.get(),
            "port": int(self.port_entry.get()) if self.port_entry.get().isdigit() else 22,
            "username": self.user_entry.get(),
            "password": self.pwd_entry.get(),
        }


class ScenarioParamsPanel(ttk.LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Scenario Parameters (shared)", padding=10, **kwargs)
        self._build()

    def _build(self):
        row = ttk.Frame(self)
        row.pack(fill=tk.X)
        self.request_len_entry = LabeledEntry(row, "Request Length:", "1024", width=12)
        self.request_len_entry.pack(side=tk.LEFT, padx=(0, 20))
        self.concurrency_entry = LabeledEntry(row, "Concurrency:", "1", width=12)
        self.concurrency_entry.pack(side=tk.LEFT, padx=(0, 20))

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
