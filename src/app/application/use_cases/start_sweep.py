from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import numpy as np

from app.application.dto import StartSweepCommand
from app.application.events import (
    EventEmitter,
    SweepCompleted,
    SweepDataUpdated,
    SweepFailed,
    SweepProgress,
    SweepStarted,
    SweepStopped,
    SweepWarning,
)
from app.domain.calibration import apply_reference_to_point
from app.domain.enums import CorrectionMode, TriggerMode
from app.domain.models import SweepPoint, SweepResult
from app.domain.signal_processing import calc_vin_peak, measure_dual_channel, measure_single_channel
from app.domain.sweep_engine import compute_sampling_window_s, generate_frequency_points
from app.domain.validators import ValidationError, validate_settings
from app.infrastructure.instruments.ports import AwgPort, OscPort


class StartSweepUseCase:
    def __init__(self, awg: AwgPort, osc: OscPort, stop_event: threading.Event) -> None:
        self._awg = awg
        self._osc = osc
        self._stop_event = stop_event

    def run(self, cmd: StartSweepCommand, emitter: EventEmitter) -> SweepResult:
        try:
            validate_settings(cmd.settings)
            result = SweepResult(
                meta={
                    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "freq_unit": cmd.settings.freq_unit,
                    "schema_version": cmd.settings.schema_version,
                }
            )

            settings = cmd.settings
            sweep = settings.sweep
            setup = settings.setup
            run_mode = settings.run_mode

            freq_points = generate_frequency_points(sweep)
            emitter.emit(SweepStarted(total_points=len(freq_points)))

            self._configure_instruments(cmd, emitter)

            for index, target_freq in enumerate(freq_points, start=1):
                if self._stop_event.is_set():
                    result.meta["stopped_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    emitter.emit(SweepStopped(result=result))
                    return result

                awg_ch = setup.channels.awg_ch
                self._awg.set_frequency(float(target_freq), awg_ch)
                actual_freq = self._awg.get_frequency(awg_ch)

                if not np.isclose(actual_freq, target_freq, atol=1e-3, rtol=5e-6):
                    emitter.emit(
                        SweepWarning(
                            code="FREQ_MISMATCH",
                            message=(
                                f"Requested {target_freq:.6f} Hz, actual {actual_freq:.6f} Hz"
                            ),
                        )
                    )

                requested_amp = float(setup.awg_settings.amplitude_vpp)
                read_amp = self._awg.get_amplitude_vpp(awg_ch)
                if not np.isclose(read_amp, requested_amp, atol=1e-2, rtol=1e-3):
                    emitter.emit(
                        SweepWarning(
                            code="AMP_MISMATCH",
                            message=(
                                f"Requested {requested_amp:.6f} Vpp, actual {read_amp:.6f} Vpp"
                            ),
                        )
                    )

                sample_rate = self._osc.get_sample_rate()
                window_s = compute_sampling_window_s(
                    freq_hz=actual_freq,
                    sample_rate_hz=sample_rate,
                    points=setup.osc_settings.points,
                )

                self._osc.set_timebase(window_s)
                triggered = run_mode.trigger_mode == TriggerMode.TRIGGERED
                self._osc.single_acquire(triggered=triggered)

                test_ch = setup.channels.osc_test_ch
                times_t, volts_t = self._osc.read_waveform(test_ch, setup.osc_settings.points)

                if run_mode.auto_range and self._adjust_auto_range(test_ch, volts_t, setup.osc_settings.offset_v):
                    self._osc.single_acquire(triggered=triggered)
                    times_t, volts_t = self._osc.read_waveform(test_ch, setup.osc_settings.points)

                if run_mode.correction_mode == CorrectionMode.DUAL:
                    ref_ch = int(setup.channels.osc_ref_ch or test_ch)
                    times_r, volts_r = self._osc.read_waveform(ref_ch, setup.osc_settings.points)
                    gain_linear, gain_db, phase_deg, gain_complex = measure_dual_channel(
                        times_t,
                        volts_t,
                        times_r,
                        volts_r,
                        actual_freq,
                    )
                else:
                    vin_peak = calc_vin_peak(
                        vpp_panel=read_amp,
                        awg_impedance=setup.awg_settings.impedance.value,
                        osc_impedance=setup.osc_settings.impedance.value,
                    )
                    gain_linear, gain_db, phase_deg, gain_complex = measure_single_channel(
                        times_t,
                        volts_t,
                        actual_freq,
                        vin_peak,
                        compute_phase=triggered,
                    )

                point = SweepPoint(
                    freq_hz=float(actual_freq),
                    gain_linear=float(gain_linear),
                    gain_db=float(gain_db),
                    phase_deg=float(phase_deg) if phase_deg is not None else None,
                    gain_complex=complex(gain_complex) if gain_complex is not None else None,
                )

                if cmd.calibration_enabled and cmd.reference_interpolator is not None:
                    use_phase = (
                        run_mode.correction_mode == CorrectionMode.DUAL
                        or run_mode.trigger_mode == TriggerMode.TRIGGERED
                    )
                    ref_value = cmd.reference_interpolator(np.array([point.freq_hz]))[0]
                    point = apply_reference_to_point(point, ref_value, use_phase=use_phase)

                result.append(point)

                emitter.emit(SweepProgress(freq_hz=point.freq_hz, point_index=index, total_points=len(freq_points)))
                emitter.emit(SweepDataUpdated(last_point=point, partial_result=result))

                # Give stop signals a chance to be observed in long hardware loops.
                time.sleep(0.001)

            result.meta["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            emitter.emit(SweepCompleted(result=result))
            return result

        except ValidationError as exc:
            emitter.emit(SweepFailed(error_code="VALIDATION", message=str(exc)))
            return SweepResult()
        except Exception as exc:  # noqa: BLE001
            emitter.emit(SweepFailed(error_code="SWEEP_RUNTIME", message=str(exc)))
            return SweepResult()

    def _configure_instruments(self, cmd: StartSweepCommand, emitter: EventEmitter) -> None:
        settings = cmd.settings
        setup = settings.setup
        run_mode = settings.run_mode

        awg_ch = setup.channels.awg_ch
        test_ch = setup.channels.osc_test_ch

        if run_mode.auto_reset:
            self._awg.reset()
            self._osc.reset()

        self._awg.output_on(awg_ch)
        self._awg.set_impedance(setup.awg_settings.impedance.value, awg_ch)
        self._awg.set_amplitude_vpp(setup.awg_settings.amplitude_vpp, awg_ch)

        self._osc.output_on(test_ch)
        self._osc.set_coupling(test_ch, setup.osc_settings.coupling.value)
        self._osc.set_impedance(test_ch, setup.osc_settings.impedance.value)
        self._osc.set_vertical(test_ch, setup.osc_settings.full_scale_v, setup.osc_settings.offset_v)

        if run_mode.correction_mode == CorrectionMode.DUAL and setup.channels.osc_ref_ch:
            self._osc.output_on(setup.channels.osc_ref_ch)
            self._osc.set_coupling(setup.channels.osc_ref_ch, setup.osc_settings.coupling.value)
            self._osc.set_impedance(setup.channels.osc_ref_ch, setup.osc_settings.impedance.value)
            self._osc.set_vertical(
                setup.channels.osc_ref_ch,
                setup.osc_settings.full_scale_v,
                setup.osc_settings.offset_v,
            )

        if run_mode.trigger_mode == TriggerMode.TRIGGERED:
            trig_ch = int(setup.channels.osc_trig_ch or test_ch)
            self._osc.output_on(trig_ch)
            self._osc.arm_trigger(trig_ch, level_v=0.0)
        else:
            self._osc.set_free_run()

        emitter.emit(SweepWarning(code="READY", message="Instruments configured"))

    def _adjust_auto_range(self, channel: int, volts: np.ndarray, requested_offset_v: float) -> bool:
        if volts is None or len(volts) == 0:
            return False

        vmax = float(np.max(volts))
        vmin = float(np.min(volts))
        vpp = vmax - vmin
        midpoint = (vmax + vmin) / 2.0

        current_range, current_offset = self._osc.get_vertical(channel)
        if current_range <= 0:
            return False

        ratio = vpp / current_range
        target_range = current_range
        target_offset = requested_offset_v

        if ratio > 0.85:
            target_range = vpp / 0.7
        elif 0.0 < ratio < 0.55:
            target_range = max(vpp / 0.7, current_range * 0.5)

        if abs(midpoint - current_offset) > (current_range * 0.2):
            target_offset = midpoint

        range_changed = not np.isclose(target_range, current_range, rtol=1e-2, atol=1e-3)
        offset_changed = not np.isclose(target_offset, current_offset, rtol=1e-2, atol=1e-3)

        if range_changed or offset_changed:
            self._osc.set_vertical(channel, float(target_range), float(target_offset))
            return True

        return False
