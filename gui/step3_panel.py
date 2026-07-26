import tkinter as tk
from tkinter import ttk, messagebox
import os

from gui.widgets import LabeledEntry, ScrollableLogFrame
from i18n import tr, on_lang_change


class Step3Panel(ttk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._result_data = None
        self._build()
        on_lang_change(self.refresh_language)

    def _build(self):
        self.config_frame = ttk.LabelFrame(self, text=tr("step3.config"), padding=10)
        self.config_frame.pack(fill=tk.X, padx=5, pady=5)

        self.hint_label = ttk.Label(self.config_frame, text=tr("step3.hint"),
                                    font=("", 9, "italic"))
        self.hint_label.pack(anchor=tk.W, pady=(0, 5))

        row1 = ttk.Frame(self.config_frame)
        row1.pack(fill=tk.X, pady=2)
        self.bw_entry = LabeledEntry(row1, tr("step3.bw"), "", label_width=20)
        self.bw_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.from_step1_btn = ttk.Button(row1, text=tr("step3.from_step1"), command=self._auto_fill_bw, width=10)
        self.from_step1_btn.pack(side=tk.LEFT)

        row2 = ttk.Frame(self.config_frame)
        row2.pack(fill=tk.X, pady=2)
        self.full_ttft_entry = LabeledEntry(row2, tr("step3.full_ttft"), "", label_width=24)
        self.full_ttft_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.from_step2_btn = ttk.Button(row2, text=tr("step3.from_step2"), command=self._auto_fill_ttft, width=10)
        self.from_step2_btn.pack(side=tk.LEFT)

        row3 = ttk.Frame(self.config_frame)
        row3.pack(fill=tk.X, pady=2)
        self.hbm_ttft_entry = LabeledEntry(row3, tr("step3.hbm_ttft"), "", label_width=20)
        self.hbm_ttft_entry.pack(side=tk.LEFT, padx=(0, 5))

        row4 = ttk.Frame(self.config_frame)
        row4.pack(fill=tk.X, pady=2)
        self.output_dir_entry = LabeledEntry(row4, tr("step3.output_dir"), "./results/step3")
        self.output_dir_entry.pack(side=tk.LEFT, padx=(0, 5))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        self.analyze_btn = ttk.Button(btn_frame, text=tr("step3.analyze"), command=self._on_analyze)
        self.analyze_btn.pack(side=tk.LEFT, padx=5)

        self.log_frame = ScrollableLogFrame(self, height=8)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.result_frame = ttk.LabelFrame(self, text=tr("step3.result_title"), padding=10)
        self.result_frame.pack(fill=tk.X, padx=5, pady=5)

        self.ttft_range_var = tk.StringVar(value=tr("step3.range_default"))
        ttk.Label(self.result_frame, textvariable=self.ttft_range_var,
                  font=("Consolas", 11, "bold"), foreground="#d4380d").pack(anchor=tk.W, pady=3)

        self.ttft_avg_var = tk.StringVar(value=tr("step3.avg_default"))
        ttk.Label(self.result_frame, textvariable=self.ttft_avg_var,
                  font=("Consolas", 10), foreground="blue").pack(anchor=tk.W, pady=2)

        self.ratio_var = tk.StringVar(value=tr("step3.ratio_default"))
        ttk.Label(self.result_frame, textvariable=self.ratio_var,
                  font=("Consolas", 10), foreground="green").pack(anchor=tk.W, pady=2)

    def _auto_fill_bw(self):
        if self.app.step1_panel:
            bw = self.app.step1_panel.get_bandwidth()
            if bw:
                self.bw_entry.set(f"{bw:.2f}")
            else:
                messagebox.showinfo(tr("title.info"), tr("msg.step1_no_bw"))

    def _auto_fill_ttft(self):
        if self.app.step2_panel:
            full_ttft = self.app.step2_panel.get_full_ttft()
            hbm_ttft = self.app.step2_panel.get_hbm_ttft()
            if full_ttft:
                self.full_ttft_entry.set(f"{full_ttft:.2f}")
            if hbm_ttft:
                self.hbm_ttft_entry.set(f"{hbm_ttft:.2f}")
            if not full_ttft and not hbm_ttft:
                messagebox.showinfo(tr("title.info"), tr("msg.step2_no_ttft"))

    def _on_analyze(self):
        try:
            bw = float(self.bw_entry.get()) if self.bw_entry.get() else 0
            full_ttft = float(self.full_ttft_entry.get()) if self.full_ttft_entry.get() else 0
            hbm_ttft = float(self.hbm_ttft_entry.get()) if self.hbm_ttft_entry.get() else 0
        except ValueError:
            messagebox.showerror(tr("title.error"), tr("msg.invalid_numbers"))
            return

        self.log_frame.clear()
        from core.analyzer import Analyzer

        def log(msg):
            self.log_frame.append(msg)
            if self.app.log_mgr:
                self.app.log_mgr.log(msg)

        analyzer = Analyzer(log)
        result = analyzer.analyze(
            bandwidth_gbs=bw,
            full_prefill_ttft_ms=full_ttft,
            hbm_pc_ttft_ms=hbm_ttft,
            output_dir=self.output_dir_entry.get() or "./results/step3",
        )

        if result:
            self._result_data = {
                "lo": result["ucm_pc_ttft_range_ms"][0],
                "hi": result["ucm_pc_ttft_range_ms"][1],
                "avg": result["ucm_pc_ttft_avg_ms"],
                "ratio": result["ttft_ratio"],
            }
        else:
            self._result_data = None
        self._format_result()

        if result:
            rng = result["ucm_pc_ttft_range_ms"]
            messagebox.showinfo(
                tr("title.analysis_complete"),
                tr("step3.range", lo=rng[0], hi=rng[1]) + "\n"
                + tr("step3.avg", v=result["ucm_pc_ttft_avg_ms"]),
            )

    def _format_result(self):
        if self._result_data:
            d = self._result_data
            self.ttft_range_var.set(tr("step3.range", lo=d["lo"], hi=d["hi"]))
            self.ttft_avg_var.set(tr("step3.avg", v=d["avg"]))
            self.ratio_var.set(tr("step3.ratio", v=d["ratio"]))
        else:
            self.ttft_range_var.set(tr("step3.range_default"))
            self.ttft_avg_var.set(tr("step3.avg_default"))
            self.ratio_var.set(tr("step3.ratio_default"))

    def refresh_language(self):
        self.config_frame.configure(text=tr("step3.config"))
        self.hint_label.configure(text=tr("step3.hint"))
        self.bw_entry.set_label(tr("step3.bw"))
        self.from_step1_btn.configure(text=tr("step3.from_step1"))
        self.full_ttft_entry.set_label(tr("step3.full_ttft"))
        self.from_step2_btn.configure(text=tr("step3.from_step2"))
        self.hbm_ttft_entry.set_label(tr("step3.hbm_ttft"))
        self.output_dir_entry.set_label(tr("step3.output_dir"))
        self.analyze_btn.configure(text=tr("step3.analyze"))
        self.result_frame.configure(text=tr("step3.result_title"))
        self._format_result()
