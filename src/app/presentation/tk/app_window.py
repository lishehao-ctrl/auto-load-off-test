from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from mapping import Mapping

from app.presentation.tk.plot_widget import PlotWidget
from app.presentation.tk.view_model import ViewModel


class AppWindow(tk.Tk):
    def __init__(self, vm: ViewModel | None = None) -> None:
        super().__init__()
        self.vm = vm or ViewModel(self)
        self.title("LoadoffTest - Decoupled")
        self.geometry("1400x900")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._on_close = None

        container = tk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(container)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        right = tk.Frame(container)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._build_controls(left)

        self.plot_widget = PlotWidget(right)
        self.plot_widget.frame.pack(fill=tk.BOTH, expand=True)

        status_bar = tk.Frame(self)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lb_status = tk.Label(status_bar, textvariable=self.vm.status_text, anchor="w")
        self.lb_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.canvas_awg = tk.Canvas(status_bar, width=14, height=14)
        self.canvas_awg.pack(side=tk.RIGHT, padx=6)
        self.awg_light = self.canvas_awg.create_oval(2, 2, 12, 12, fill="red")
        tk.Label(status_bar, text="AWG").pack(side=tk.RIGHT)

        self.canvas_osc = tk.Canvas(status_bar, width=14, height=14)
        self.canvas_osc.pack(side=tk.RIGHT, padx=6)
        self.osc_light = self.canvas_osc.create_oval(2, 2, 12, 12, fill="red")
        tk.Label(status_bar, text="OSC").pack(side=tk.RIGHT)

    def _build_controls(self, parent: tk.Misc) -> None:
        row = 0

        def add_label(text: str, r: int, c: int = 0) -> None:
            tk.Label(parent, text=text).grid(row=r, column=c, sticky="w", padx=3, pady=2)

        add_label("AWG model", row)
        ttk.Combobox(parent, textvariable=self.vm.awg_model, values=Mapping.values_awg, width=12).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("OSC model", row)
        ttk.Combobox(parent, textvariable=self.vm.osc_model, values=Mapping.values_osc, width=12).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("AWG conn", row)
        ttk.Combobox(parent, textvariable=self.vm.awg_connect_mode, values=["auto", "lan"], width=12).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("AWG VISA", row)
        tk.Entry(parent, textvariable=self.vm.awg_visa, width=28).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("AWG IP", row)
        tk.Entry(parent, textvariable=self.vm.awg_ip, width=28).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC conn", row)
        ttk.Combobox(parent, textvariable=self.vm.osc_connect_mode, values=["auto", "lan"], width=12).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("OSC VISA", row)
        tk.Entry(parent, textvariable=self.vm.osc_visa, width=28).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC IP", row)
        tk.Entry(parent, textvariable=self.vm.osc_ip, width=28).grid(row=row, column=1, sticky="ew")
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        add_label("Freq unit", row)
        ttk.Combobox(parent, textvariable=self.vm.freq_unit, values=Mapping.values_freq_unit, width=8).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("Start", row)
        tk.Entry(parent, textvariable=self.vm.start_freq).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("Stop", row)
        tk.Entry(parent, textvariable=self.vm.stop_freq).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("Step", row)
        tk.Entry(parent, textvariable=self.vm.step_freq).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("Step count", row)
        tk.Entry(parent, textvariable=self.vm.step_count).grid(row=row, column=1, sticky="ew")
        row += 1

        tk.Checkbutton(parent, text="Log sweep", variable=self.vm.is_log).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        add_label("AWG amp (Vpp)", row)
        tk.Entry(parent, textvariable=self.vm.awg_amp).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("AWG imp", row)
        ttk.Combobox(parent, textvariable=self.vm.awg_imp, values=["50", "INF"], width=8).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC range", row)
        tk.Entry(parent, textvariable=self.vm.osc_range).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC offset", row)
        tk.Entry(parent, textvariable=self.vm.osc_offset).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC points", row)
        tk.Entry(parent, textvariable=self.vm.osc_points).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC imp", row)
        ttk.Combobox(parent, textvariable=self.vm.osc_imp, values=["50", "INF"], width=8).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC coup", row)
        ttk.Combobox(parent, textvariable=self.vm.osc_coupling, values=["DC", "AC"], width=8).grid(row=row, column=1, sticky="ew")
        row += 1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        add_label("AWG ch", row)
        tk.Entry(parent, textvariable=self.vm.awg_ch).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC test ch", row)
        tk.Entry(parent, textvariable=self.vm.osc_test_ch).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC ref ch", row)
        tk.Entry(parent, textvariable=self.vm.osc_ref_ch).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("OSC trig ch", row)
        tk.Entry(parent, textvariable=self.vm.osc_trig_ch).grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("Correction", row)
        ttk.Combobox(parent, textvariable=self.vm.correction_mode, values=["none", "single", "dual"], width=10).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        add_label("Trigger", row)
        ttk.Combobox(parent, textvariable=self.vm.trigger_mode, values=["free_run", "triggered"], width=10).grid(
            row=row, column=1, sticky="ew"
        )
        row += 1

        tk.Checkbutton(parent, text="Auto range", variable=self.vm.auto_range).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        tk.Checkbutton(parent, text="Auto reset", variable=self.vm.auto_reset).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        tk.Checkbutton(parent, text="Enable calibration", variable=self.vm.calibration_enabled).grid(
            row=row, column=0, columnspan=2, sticky="w"
        )
        row += 1
        tk.Checkbutton(parent, text="Auto save data", variable=self.vm.auto_save_data).grid(
            row=row, column=0, columnspan=2, sticky="w"
        )
        row += 1

        add_label("Figure", row)
        self.cmb_figure = ttk.Combobox(parent, textvariable=self.vm.figure_mode, values=["gain", "gain_db"], width=10)
        self.cmb_figure.grid(row=row, column=1, sticky="ew")
        row += 1

        add_label("Display", row)
        self.cmb_mag_phase = ttk.Combobox(
            parent,
            textvariable=self.vm.magnitude_phase_mode,
            values=["magnitude", "phase", "magnitude_phase"],
            width=14,
        )
        self.cmb_mag_phase.grid(row=row, column=1, sticky="ew")
        row += 1

        buttons = tk.Frame(parent)
        buttons.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)

        self.btn_start = tk.Button(buttons, text="Start", width=9)
        self.btn_start.pack(side=tk.LEFT, padx=2)
        self.btn_stop = tk.Button(buttons, text="Stop", width=9, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=2)

        self.btn_save_data = tk.Button(buttons, text="Save Data", width=9)
        self.btn_save_data.pack(side=tk.LEFT, padx=2)
        self.btn_load_data = tk.Button(buttons, text="Load Data", width=9)
        self.btn_load_data.pack(side=tk.LEFT, padx=2)

        row += 1
        buttons2 = tk.Frame(parent)
        buttons2.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)

        self.btn_load_ref = tk.Button(buttons2, text="Load Ref", width=9)
        self.btn_load_ref.pack(side=tk.LEFT, padx=2)
        self.btn_save_settings = tk.Button(buttons2, text="Save Settings", width=11)
        self.btn_save_settings.pack(side=tk.LEFT, padx=2)
        self.btn_load_settings = tk.Button(buttons2, text="Load Settings", width=11)
        self.btn_load_settings.pack(side=tk.LEFT, padx=2)

        parent.grid_columnconfigure(1, weight=1)

    def bind_actions(
        self,
        *,
        on_start,
        on_stop,
        on_save_data,
        on_load_data,
        on_load_ref,
        on_save_settings,
        on_load_settings,
        on_close,
        on_figure_change,
        on_mag_phase_change,
    ) -> None:
        self.btn_start.configure(command=on_start)
        self.btn_stop.configure(command=on_stop)
        self.btn_save_data.configure(command=on_save_data)
        self.btn_load_data.configure(command=on_load_data)
        self.btn_load_ref.configure(command=on_load_ref)
        self.btn_save_settings.configure(command=on_save_settings)
        self.btn_load_settings.configure(command=on_load_settings)

        self.cmb_figure.bind("<<ComboboxSelected>>", lambda _e: on_figure_change())
        self.cmb_mag_phase.bind("<<ComboboxSelected>>", lambda _e: on_mag_phase_change())
        self._on_close = on_close

    def set_connection_status(self, awg_connected: bool, osc_connected: bool) -> None:
        self.canvas_awg.itemconfig(self.awg_light, fill="green" if awg_connected else "red")
        self.canvas_osc.itemconfig(self.osc_light, fill="green" if osc_connected else "red")

    def on_close(self) -> None:
        if self._on_close is not None:
            self._on_close()
        else:
            self.destroy()
