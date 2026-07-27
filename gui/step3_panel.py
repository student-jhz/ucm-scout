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
        self.bw_entry = LabeledEntry(row1, tr("step3.bw"), "", label_width=24)
        self.bw_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.from_step1_btn = ttk.Button(row1, text=tr("step3.from_step1"),
                                          command=self._auto_fill_step1, width=10)
        self.from_step1_btn.pack(side=tk.LEFT)

        row2 = ttk.Frame(self.config_frame)
        row2.pack(fill=tk.X, pady=2)
        self.full_ttft_entry = LabeledEntry(row2, tr("step3.full_ttft"), "", label_width=24)
        self.full_ttft_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.from_step2_btn = ttk.Button(row2, text=tr("step3.from_step2"),
                                          command=self._auto_fill_ttft, width=10)
        self.from_step2_btn.pack(side=tk.LEFT)

        row3 = ttk.Frame(self.config_frame)
        row3.pack(fill=tk.X, pady=2)
        self.hbm_ttft_entry = LabeledEntry(row3, tr("step3.hbm_ttft"), "", label_width=24)
        self.hbm_ttft_entry.pack(side=tk.LEFT, padx=(0, 5))

        row4 = ttk.Frame(self.config_frame)
        row4.pack(fill=tk.X, pady=2)
        self.pcie_entry = LabeledEntry(row4, tr("step3.pcie_bw"), "50.0", label_width=24)
        self.pcie_entry.pack(side=tk.LEFT, padx=(0, 5))

        row5 = ttk.Frame(self.config_frame)
        row5.pack(fill=tk.X, pady=2)
        self.shard_info_var = tk.StringVar()
        ttk.Label(row5, textvariable=self.shard_info_var,
                  font=("", 9, "italic"), foreground="gray").pack(anchor=tk.W)

        row6 = ttk.Frame(self.config_frame)
        row6.pack(fill=tk.X, pady=2)
        self.output_dir_entry = LabeledEntry(row6, tr("step3.output_dir"), "./results/step3", label_width=24)
        self.output_dir_entry.pack(side=tk.LEFT, padx=(0, 5))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        self.analyze_btn = ttk.Button(btn_frame, text=tr("step3.analyze"), command=self._on_analyze)
        self.analyze_btn.pack(side=tk.LEFT, padx=5)

        self.log_frame = ScrollableLogFrame(self, height=6)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.result_frame = ttk.LabelFrame(self, text=tr("step3.result_title"), padding=10)
        self.result_frame.pack(fill=tk.X, padx=5, pady=5)

        self.ttft_var = tk.StringVar(value=tr("step3.ucm_ttft_default"))
        ttk.Label(self.result_frame, textvariable=self.ttft_var,
                  font=("Consolas", 11, "bold"), foreground="#d4380d").pack(anchor=tk.W, pady=3)

        self.benefit_var = tk.StringVar(value=tr("step3.benefit_default"))
        ttk.Label(self.result_frame, textvariable=self.benefit_var,
                  font=("Consolas", 10), foreground="blue").pack(anchor=tk.W, pady=2)

        self.ratio_var = tk.StringVar(value=tr("step3.ratio_default"))
        ttk.Label(self.result_frame, textvariable=self.ratio_var,
                  font=("Consolas", 10), foreground="green").pack(anchor=tk.W, pady=2)

    def _auto_fill_step1(self):
        if self.app.step1_panel:
            bw = self.app.step1_panel.get_bandwidth()
            if bw:
                self.bw_entry.set(f"{bw:.2f}")
            shard_size = self.app.step1_panel.get_shard_size()
            shard_num = self.app.step1_panel.get_shard_number()
            blocks = self.app.step1_panel.get_block_number()
            if shard_size > 0:
                total_mb = shard_size * shard_num * blocks / 1e6
                self.shard_info_var.set(tr("step3.shard_info",
                    size=shard_size, num=shard_num, blocks=blocks, total_mb=total_mb))
            if not bw:
                messagebox.showinfo(tr("title.info"), tr("msg.step1_no_bw"))
            self._shard_size = shard_size
            self._shard_number = shard_num
            self._block_number = blocks
        else:
            self._shard_size = 0
            self._shard_number = 0
            self._block_number = 0

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
            pcie_bw = float(self.pcie_entry.get()) if self.pcie_entry.get() else 50.0
        except ValueError:
            messagebox.showerror(tr("title.error"), tr("msg.invalid_numbers"))
            return

        shard_size = getattr(self, "_shard_size", 0)
        shard_num = getattr(self, "_shard_number", 0)
        blocks = getattr(self, "_block_number", 0)

        self.log_frame.clear()
        from core.analyzer import Analyzer

        def log(msg):
            self.log_frame.append(msg)
            if self.app.log_mgr:
                self.app.log_mgr.log(msg)

        analyzer = Analyzer(log)
        result = analyzer.analyze(
            load_bw_gbs=bw,
            full_prefill_ttft_ms=full_ttft,
            hbm_pc_ttft_ms=hbm_ttft,
            shard_size=shard_size,
            shard_number=shard_num,
            block_number=blocks,
            pcie_bw_gbs=pcie_bw,
            output_dir=self.output_dir_entry.get() or "./results/step3",
        )

        if result:
            self._result_data = {
                "ucm_ttft": result["ucm_pc_ttft_ms"],
                "is_beneficial": result["is_beneficial"],
                "speedup": result["speedup_vs_full"],
                "slowdown": result["slowdown_vs_full"],
                "ratio_hbm": result["ratio_vs_hbm_pc"],
                "strategy": result["strategy"],
            }
        else:
            self._result_data = None
        self._format_result()

        if result and result["is_beneficial"]:
            messagebox.showinfo(tr("title.analysis_complete"),
                tr("step3.summary_ok", ucm=result["ucm_pc_ttft_ms"],
                   speedup=result["speedup_vs_full"]))
        elif result:
            messagebox.showinfo(tr("title.analysis_complete"),
                tr("step3.summary_bad", ucm=result["ucm_pc_ttft_ms"],
                   full=full_ttft))

    def _format_result(self):
        if self._result_data:
            d = self._result_data
            self.ttft_var.set(tr("step3.ucm_ttft_result", v=d["ucm_ttft"]))
            if d["is_beneficial"]:
                self.benefit_var.set(tr("step3.benefit_ok", v=d["speedup"]))
            else:
                self.benefit_var.set(tr("step3.benefit_bad", v=d["slowdown"]))
            self.ratio_var.set(tr("step3.ratio_hbm", v=d["ratio_hbm"]))
        else:
            self.ttft_var.set(tr("step3.ucm_ttft_default"))
            self.benefit_var.set(tr("step3.benefit_default"))
            self.ratio_var.set(tr("step3.ratio_default"))

    def refresh_language(self):
        self.config_frame.configure(text=tr("step3.config"))
        self.hint_label.configure(text=tr("step3.hint"))
        self.bw_entry.set_label(tr("step3.bw"))
        self.from_step1_btn.configure(text=tr("step3.from_step1"))
        self.full_ttft_entry.set_label(tr("step3.full_ttft"))
        self.from_step2_btn.configure(text=tr("step3.from_step2"))
        self.hbm_ttft_entry.set_label(tr("step3.hbm_ttft"))
        self.pcie_entry.set_label(tr("step3.pcie_bw"))
        self.output_dir_entry.set_label(tr("step3.output_dir"))
        self.analyze_btn.configure(text=tr("step3.analyze"))
        self.result_frame.configure(text=tr("step3.result_title"))
        self._format_result()
