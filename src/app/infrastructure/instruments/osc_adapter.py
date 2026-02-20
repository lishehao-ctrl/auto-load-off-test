from __future__ import annotations

import numpy as np

class EquipsOscAdapter:
    def __init__(self, model: str, visa_address: str) -> None:
        try:
            from equips import inst_mapping
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing runtime dependency: pyvisa/equips is required for instrument access"
            ) from exc

        if model not in inst_mapping:
            raise ValueError(f"Unsupported OSC model: {model}")
        self._inst = inst_mapping[model](name=model, visa_address=visa_address)

    def reset(self) -> None:
        self._inst.rst()

    def output_on(self, channel: int) -> None:
        self._inst.set_on(ch=channel)

    def set_timebase(self, window_s: float, offset_s: float | None = None) -> None:
        xscale = float(window_s) / 10.0
        self._inst.set_x(xscale=xscale, xoffset=offset_s)

    def set_vertical(self, channel: int, full_scale_v: float, offset_v: float) -> None:
        yscale = float(full_scale_v) / 8.0
        self._inst.set_y(ch=channel, yscale=yscale, yoffset=float(offset_v))

    def get_vertical(self, channel: int) -> tuple[float, float]:
        yscale, yoffset = self._inst.get_y(ch=channel)
        return float(yscale) * 8.0, float(yoffset)

    def set_coupling(self, channel: int, mode: str) -> None:
        self._inst.set_coup(coup=mode, ch=channel)

    def set_impedance(self, channel: int, mode: str) -> None:
        self._inst.set_imp(imp=mode, ch=channel)

    def arm_trigger(self, channel: int, level_v: float) -> None:
        self._inst.set_trig_rise(ch=channel, level=float(level_v))

    def set_free_run(self) -> None:
        self._inst.set_free_run()

    def single_acquire(self, triggered: bool) -> None:
        if triggered:
            self._inst.trig_measure()
        else:
            self._inst.quick_measure()

    def read_waveform(self, channel: int, points: int | None) -> tuple[np.ndarray, np.ndarray]:
        request_points = points if points and points > 0 else 10_000
        times, volts = self._inst.read_raw_waveform(ch=channel, points=request_points)
        return np.asarray(times, dtype=float), np.asarray(volts, dtype=float)

    def get_sample_rate(self) -> float:
        return float(self._inst.get_sample_rate())

    def close(self) -> None:
        try:
            self._inst.inst_close()
        except Exception:
            pass
