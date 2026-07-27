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


class RemoteDirBrowser(tk.Toplevel):
    def __init__(self, parent, ssh_client, title="Remote Directory", **kwargs):
        super().__init__(parent, **kwargs)
        self.ssh = ssh_client
        self.title(title)
        self.geometry("600x450")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.result = None
        self._current_path = "/"
        self._build()

    def _build(self):
        nav_frame = ttk.Frame(self)
        nav_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Button(nav_frame, text="Up", width=4, command=self._go_up).pack(side=tk.LEFT, padx=(0, 5))
        self.path_var = tk.StringVar(value="/")
        self.path_entry = ttk.Entry(nav_frame, textvariable=self.path_var, width=60)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.path_entry.bind("<Return>", lambda e: self._navigate(self.path_var.get()))
        ttk.Button(nav_frame, text="Go", width=4, command=lambda: self._navigate(self.path_var.get())).pack(side=tk.LEFT)

        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.dir_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Consolas", 10),
                                       selectmode=tk.SINGLE, activestyle="none")
        scrollbar.configure(command=self.dir_listbox.yview)
        self.dir_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.dir_listbox.bind("<Double-Button-1>", self._on_double_click)
        self.dir_listbox.bind("<Return>", self._on_double_click)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        self.status_label = ttk.Label(btn_frame, text="", foreground="gray")
        self.status_label.pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Select", command=self._on_select).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)

        self._navigate("/")

    def _go_up(self):
        parent = self._current_path.rstrip("/")
        if parent:
            parent = "/".join(parent.split("/")[:-1]) or "/"
        else:
            parent = "/"
        self._navigate(parent)

    def _on_double_click(self, event):
        sel = self.dir_listbox.curselection()
        if sel:
            entry = self.dir_listbox.get(sel[0])
            name = entry[2:].strip()
            if entry.startswith("D "):
                new_path = self._current_path.rstrip("/") + "/" + name
                new_path = new_path.replace("//", "/")
                self._navigate(new_path)

    def _on_select(self):
        self.result = self._current_path
        self.destroy()

    def _navigate(self, path):
        path = path.rstrip("/") or "/"

        def _fetch():
            code, out, _ = self.ssh.execute(
                f"ls -1p '{path}' 2>/dev/null | head -200", timeout=10)
            if code != 0:
                self._current_path = path
                self.after(0, lambda: self._update_list([]))
                self.after(0, lambda: self.status_label.configure(
                    text=f"Error reading {path}"))
                return
            entries = []
            for line in out.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line.endswith("/"):
                    entries.append(("D", line[:-1]))
                else:
                    entries.append(("F", line))
            self._current_path = path
            self.after(0, lambda: self._update_list(entries))
            self.after(0, lambda: self.status_label.configure(text=f"{path}"))

        self.status_label.configure(text="Loading...")
        self.dir_listbox.delete(0, tk.END)
        self.dir_listbox.insert(tk.END, "  Loading...")
        import threading
        threading.Thread(target=_fetch, daemon=True).start()

    def _update_list(self, entries):
        self.dir_listbox.delete(0, tk.END)
        self.path_var.set(self._current_path)
        for typ, name in entries:
            prefix = "D " if typ == "D" else "  "
            self.dir_listbox.insert(tk.END, f"{prefix}{name}")

    def show(self):
        self.wait_window()
        return self.result
