from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.domain.enums import (
    ConnectionMode,
    CorrectionMode,
    CouplingMode,
    ImpedanceMode,
    MagnitudePhaseMode,
    TriggerMode,
)


@dataclass(slots=True)
class SweepSpec:
    start_hz: float
    stop_hz: float
    step_hz: float | None
    step_count: int | None
    is_log: bool


@dataclass(slots=True)
class ChannelSelection:
    awg_ch: int
    osc_test_ch: int
    osc_ref_ch: int | None = None
    osc_trig_ch: int | None = None


@dataclass(slots=True)
class RunMode:
    correction_mode: CorrectionMode
    trigger_mode: TriggerMode
    auto_range: bool
    auto_reset: bool


@dataclass(slots=True)
class InstrumentEndpoint:
    model: str
    connect_mode: ConnectionMode
    visa_address: str = ""
    ip_address: str = "0.0.0.0"


@dataclass(slots=True)
class AwgSettings:
    amplitude_vpp: float
    impedance: ImpedanceMode


@dataclass(slots=True)
class OscSettings:
    full_scale_v: float
    offset_v: float
    points: int
    impedance: ImpedanceMode
    coupling: CouplingMode


@dataclass(slots=True)
class InstrumentSetup:
    awg: InstrumentEndpoint
    osc: InstrumentEndpoint
    channels: ChannelSelection
    awg_settings: AwgSettings
    osc_settings: OscSettings


@dataclass(slots=True)
class SweepPoint:
    freq_hz: float
    gain_linear: float
    gain_db: float
    phase_deg: float | None = None
    gain_complex: complex | None = None


@dataclass(slots=True)
class SweepResult:
    points: list[SweepPoint] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def append(self, point: SweepPoint) -> None:
        self.points.append(point)

    @property
    def is_empty(self) -> bool:
        return len(self.points) == 0

    def freq_array(self) -> np.ndarray:
        return np.array([p.freq_hz for p in self.points], dtype=float)

    def gain_array(self) -> np.ndarray:
        return np.array([p.gain_linear for p in self.points], dtype=float)

    def gain_db_array(self) -> np.ndarray:
        return np.array([p.gain_db for p in self.points], dtype=float)

    def phase_array(self) -> np.ndarray:
        phase = [p.phase_deg for p in self.points if p.phase_deg is not None]
        return np.array(phase, dtype=float)

    def gain_complex_array(self) -> np.ndarray:
        values = [p.gain_complex for p in self.points if p.gain_complex is not None]
        return np.array(values, dtype=np.complex128)


@dataclass(slots=True)
class ReferenceCurve:
    freq_hz: np.ndarray
    gain_db: np.ndarray
    phase_deg: np.ndarray | None = None


@dataclass(slots=True)
class PlotData:
    freq_hz: np.ndarray
    gain_linear: np.ndarray
    gain_db: np.ndarray
    phase_deg: np.ndarray | None


@dataclass(slots=True)
class AppSettings:
    schema_version: int
    freq_unit: str
    sweep: SweepSpec
    run_mode: RunMode
    setup: InstrumentSetup
    magnitude_phase_mode: MagnitudePhaseMode
    auto_save_data: bool
