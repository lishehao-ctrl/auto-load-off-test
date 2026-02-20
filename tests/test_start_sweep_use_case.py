from __future__ import annotations

import sys
from pathlib import Path
import threading
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.dto import StartSweepCommand
from app.application.events import SweepCompleted, SweepProgress, SweepStarted, SweepStopped
from app.application.use_cases.start_sweep import StartSweepUseCase
from app.domain.enums import (
    ConnectionMode,
    CorrectionMode,
    CouplingMode,
    ImpedanceMode,
    MagnitudePhaseMode,
    TriggerMode,
)
from app.domain.models import (
    AppSettings,
    AwgSettings,
    ChannelSelection,
    InstrumentEndpoint,
    InstrumentSetup,
    OscSettings,
    RunMode,
    SweepSpec,
)


class MockAwg:
    def __init__(self) -> None:
        self.freq = 1_000.0
        self.amp = 1.0

    def reset(self) -> None:
        return None

    def output_on(self, channel: int) -> None:
        _ = channel

    def set_impedance(self, mode: str, channel: int) -> None:
        _ = (mode, channel)

    def set_frequency(self, hz: float, channel: int) -> None:
        _ = channel
        self.freq = hz

    def get_frequency(self, channel: int) -> float:
        _ = channel
        return self.freq

    def set_amplitude_vpp(self, vpp: float, channel: int) -> None:
        _ = channel
        self.amp = vpp

    def get_amplitude_vpp(self, channel: int) -> float:
        _ = channel
        return self.amp

    def close(self) -> None:
        return None


class MockOsc:
    def __init__(self, awg: MockAwg) -> None:
        self._awg = awg
        self._range = 1.0
        self._offset = 0.0

    def reset(self) -> None:
        return None

    def output_on(self, channel: int) -> None:
        _ = channel

    def set_timebase(self, window_s: float, offset_s: float | None = None) -> None:
        _ = (window_s, offset_s)

    def set_vertical(self, channel: int, full_scale_v: float, offset_v: float) -> None:
        _ = channel
        self._range = full_scale_v
        self._offset = offset_v

    def get_vertical(self, channel: int) -> tuple[float, float]:
        _ = channel
        return self._range, self._offset

    def set_coupling(self, channel: int, mode: str) -> None:
        _ = (channel, mode)

    def set_impedance(self, channel: int, mode: str) -> None:
        _ = (channel, mode)

    def arm_trigger(self, channel: int, level_v: float) -> None:
        _ = (channel, level_v)

    def set_free_run(self) -> None:
        return None

    def single_acquire(self, triggered: bool) -> None:
        _ = triggered

    def read_waveform(self, channel: int, points: int | None) -> tuple[np.ndarray, np.ndarray]:
        _ = channel
        n = points or 5000
        sr = 200_000
        t = np.arange(0.0, n / sr, 1.0 / sr)
        volts = 0.5 * np.sin(2.0 * np.pi * self._awg.freq * t)
        return t, volts

    def get_sample_rate(self) -> float:
        return 200_000.0

    def close(self) -> None:
        return None


class Recorder:
    def __init__(self) -> None:
        self.events: list[object] = []

    def emit(self, event: object) -> None:
        self.events.append(event)


class StartSweepUseCaseTests(unittest.TestCase):
    def _build_settings(self) -> AppSettings:
        return AppSettings(
            schema_version=1,
            freq_unit="Hz",
            sweep=SweepSpec(start_hz=1000.0, stop_hz=3000.0, step_hz=1000.0, step_count=None, is_log=False),
            run_mode=RunMode(
                correction_mode=CorrectionMode.NONE,
                trigger_mode=TriggerMode.FREE_RUN,
                auto_range=False,
                auto_reset=True,
            ),
            setup=InstrumentSetup(
                awg=InstrumentEndpoint(model="DSG4102", connect_mode=ConnectionMode.AUTO),
                osc=InstrumentEndpoint(model="MDO34", connect_mode=ConnectionMode.AUTO),
                channels=ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=2, osc_trig_ch=2),
                awg_settings=AwgSettings(amplitude_vpp=1.0, impedance=ImpedanceMode.R50),
                osc_settings=OscSettings(
                    full_scale_v=1.0,
                    offset_v=0.0,
                    points=4000,
                    impedance=ImpedanceMode.R50,
                    coupling=CouplingMode.DC,
                ),
            ),
            magnitude_phase_mode=MagnitudePhaseMode.MAG,
            auto_save_data=False,
        )

    def test_run_emits_started_progress_completed(self) -> None:
        awg = MockAwg()
        osc = MockOsc(awg)
        stop_event = threading.Event()

        use_case = StartSweepUseCase(awg=awg, osc=osc, stop_event=stop_event)
        recorder = Recorder()

        result = use_case.run(StartSweepCommand(settings=self._build_settings()), recorder)

        self.assertFalse(result.is_empty)
        self.assertTrue(any(isinstance(e, SweepStarted) for e in recorder.events))
        self.assertTrue(any(isinstance(e, SweepCompleted) for e in recorder.events))

        progress_count = sum(1 for e in recorder.events if isinstance(e, SweepProgress))
        self.assertEqual(progress_count, 3)

    def test_run_can_be_stopped(self) -> None:
        awg = MockAwg()
        osc = MockOsc(awg)
        stop_event = threading.Event()
        stop_event.set()

        use_case = StartSweepUseCase(awg=awg, osc=osc, stop_event=stop_event)
        recorder = Recorder()

        result = use_case.run(StartSweepCommand(settings=self._build_settings()), recorder)

        self.assertTrue(any(isinstance(e, SweepStopped) for e in recorder.events))
        self.assertTrue(result.is_empty or len(result.points) >= 0)


if __name__ == "__main__":
    unittest.main()
