from __future__ import annotations

import tkinter as tk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from cvtTools import CvtTools
from mapping import Mapping

from app.domain.models import SweepResult


class PlotWidget:
    def __init__(self, parent: tk.Misc) -> None:
        self.frame = tk.Frame(parent)

        self._fig_gain = Figure(figsize=(8, 4))
        self._ax_gain = self._fig_gain.add_subplot(111)
        self._ax_gain.set_ylabel("Gain")
        (self._line_gain,) = self._ax_gain.plot([], [], "-")

        self._ax_gain_right = self._ax_gain.twinx()
        self._ax_gain_right.set_ylabel("Phase (deg)")
        (self._line_phase_gain,) = self._ax_gain_right.plot([], [], ":", color=Mapping.mapping_color_for_phase_line)

        self._canvas_gain = FigureCanvasTkAgg(self._fig_gain, master=self.frame)
        self._canvas_gain.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self._fig_db = Figure(figsize=(8, 4))
        self._ax_db = self._fig_db.add_subplot(111)
        self._ax_db.set_ylabel("Gain (dB)")
        (self._line_db,) = self._ax_db.plot([], [], "-")

        self._ax_db_right = self._ax_db.twinx()
        self._ax_db_right.set_ylabel("Phase (deg)")
        (self._line_phase_db,) = self._ax_db_right.plot([], [], ":", color=Mapping.mapping_color_for_phase_line)

        self._canvas_db = FigureCanvasTkAgg(self._fig_db, master=self.frame)

    def set_mode(self, mode: str) -> None:
        if mode == "gain_db":
            self._canvas_gain.get_tk_widget().pack_forget()
            self._canvas_db.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        else:
            self._canvas_db.get_tk_widget().pack_forget()
            self._canvas_gain.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_result(self, result: SweepResult, freq_unit: str, mag_phase_mode: str) -> None:
        freq_hz = np.array([p.freq_hz for p in result.points], dtype=float)
        gain = np.array([p.gain_linear for p in result.points], dtype=float)
        gain_db = np.array([p.gain_db for p in result.points], dtype=float)

        phase_x: list[float] = []
        phase_y: list[float] = []
        for p in result.points:
            if p.phase_deg is not None:
                phase_x.append(p.freq_hz)
                phase_y.append(p.phase_deg)

        scale = CvtTools.convert_general_unit(freq_unit)
        x = freq_hz / scale if len(freq_hz) else np.array([])
        px = np.array(phase_x, dtype=float) / scale if phase_x else np.array([])
        py = np.array(phase_y, dtype=float) if phase_y else np.array([])

        self._line_gain.set_data(x, gain)
        self._line_db.set_data(x, gain_db)
        self._line_phase_gain.set_data(px, py)
        self._line_phase_db.set_data(px, py)

        if mag_phase_mode == "magnitude":
            self._line_gain.set_visible(True)
            self._line_db.set_visible(True)
            self._line_phase_gain.set_visible(False)
            self._line_phase_db.set_visible(False)
        elif mag_phase_mode == "phase":
            self._line_gain.set_visible(False)
            self._line_db.set_visible(False)
            self._line_phase_gain.set_visible(True)
            self._line_phase_db.set_visible(True)
        else:
            self._line_gain.set_visible(True)
            self._line_db.set_visible(True)
            self._line_phase_gain.set_visible(True)
            self._line_phase_db.set_visible(True)

        self._ax_gain.set_xlabel(f"Frequency ({freq_unit})")
        self._ax_db.set_xlabel(f"Frequency ({freq_unit})")

        self._ax_gain.relim()
        self._ax_gain.autoscale_view()
        self._ax_gain_right.relim()
        self._ax_gain_right.autoscale_view()

        self._ax_db.relim()
        self._ax_db.autoscale_view()
        self._ax_db_right.relim()
        self._ax_db_right.autoscale_view()

        self._canvas_gain.draw_idle()
        self._canvas_db.draw_idle()

    def figures(self) -> dict[str, Figure]:
        return {"gain": self._fig_gain, "db": self._fig_db}
