from __future__ import annotations

from app.domain.enums import CorrectionMode, CouplingMode, ImpedanceMode, TriggerMode
from app.domain.models import AppSettings, ChannelSelection, OscSettings, SweepSpec


class ValidationError(ValueError):
    pass


def validate_sweep_spec(spec: SweepSpec) -> None:
    if spec.start_hz <= 0:
        raise ValidationError("start_hz must be > 0")
    if spec.stop_hz <= 0:
        raise ValidationError("stop_hz must be > 0")
    if spec.stop_hz < spec.start_hz:
        raise ValidationError("stop_hz must be >= start_hz")

    if spec.is_log:
        if not spec.step_count or spec.step_count <= 0:
            raise ValidationError("step_count must be > 0 for logarithmic sweep")
    else:
        if not spec.step_hz or spec.step_hz <= 0:
            raise ValidationError("step_hz must be > 0 for linear sweep")


def validate_channels(channels: ChannelSelection, correction_mode: CorrectionMode, trigger_mode: TriggerMode) -> None:
    if channels.awg_ch <= 0 or channels.osc_test_ch <= 0:
        raise ValidationError("Channel index must be positive")

    if correction_mode == CorrectionMode.DUAL and not channels.osc_ref_ch:
        raise ValidationError("osc_ref_ch is required for dual correction")
    if trigger_mode == TriggerMode.TRIGGERED and not channels.osc_trig_ch:
        raise ValidationError("osc_trig_ch is required for triggered mode")


def validate_osc_settings(settings: OscSettings) -> None:
    if settings.points <= 1:
        raise ValidationError("osc points must be > 1")
    if settings.full_scale_v <= 0:
        raise ValidationError("osc full_scale_v must be > 0")

    if settings.impedance == ImpedanceMode.R50 and settings.coupling == CouplingMode.AC:
        raise ValidationError("50-ohm impedance does not support AC coupling")


def validate_settings(settings: AppSettings) -> None:
    validate_sweep_spec(settings.sweep)
    validate_osc_settings(settings.setup.osc_settings)
    validate_channels(
        settings.setup.channels,
        settings.run_mode.correction_mode,
        settings.run_mode.trigger_mode,
    )
