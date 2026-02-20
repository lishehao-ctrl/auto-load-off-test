from __future__ import annotations

from cvtTools import CvtTools

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
from app.presentation.tk.view_model import ViewModel



def _safe_int(value: str, default: int) -> int:
    parsed = CvtTools.parse_general_val(value)
    try:
        return int(parsed)
    except Exception:
        return default



def vm_to_settings(vm: ViewModel) -> AppSettings:
    freq_unit = vm.freq_unit.get()
    is_log = bool(vm.is_log.get())

    start_hz = float(CvtTools.parse_to_hz(vm.start_freq.get(), freq_unit))
    stop_hz = float(CvtTools.parse_to_hz(vm.stop_freq.get(), freq_unit))

    step_hz = None if is_log else float(CvtTools.parse_to_hz(vm.step_freq.get(), freq_unit))
    step_count = _safe_int(vm.step_count.get(), 100) if is_log else None

    correction_mode = CorrectionMode(vm.correction_mode.get())
    trigger_mode = TriggerMode(vm.trigger_mode.get())

    return AppSettings(
        schema_version=1,
        freq_unit=freq_unit,
        sweep=SweepSpec(
            start_hz=start_hz,
            stop_hz=stop_hz,
            step_hz=step_hz,
            step_count=step_count,
            is_log=is_log,
        ),
        run_mode=RunMode(
            correction_mode=correction_mode,
            trigger_mode=trigger_mode,
            auto_range=bool(vm.auto_range.get()),
            auto_reset=bool(vm.auto_reset.get()),
        ),
        setup=InstrumentSetup(
            awg=InstrumentEndpoint(
                model=vm.awg_model.get(),
                connect_mode=ConnectionMode(vm.awg_connect_mode.get()),
                visa_address=vm.awg_visa.get().strip(),
                ip_address=vm.awg_ip.get().strip(),
            ),
            osc=InstrumentEndpoint(
                model=vm.osc_model.get(),
                connect_mode=ConnectionMode(vm.osc_connect_mode.get()),
                visa_address=vm.osc_visa.get().strip(),
                ip_address=vm.osc_ip.get().strip(),
            ),
            channels=ChannelSelection(
                awg_ch=_safe_int(vm.awg_ch.get(), 1),
                osc_test_ch=_safe_int(vm.osc_test_ch.get(), 1),
                osc_ref_ch=_safe_int(vm.osc_ref_ch.get(), 2),
                osc_trig_ch=_safe_int(vm.osc_trig_ch.get(), 2),
            ),
            awg_settings=AwgSettings(
                amplitude_vpp=float(CvtTools.parse_to_Vpp(vm.awg_amp.get())),
                impedance=ImpedanceMode(vm.awg_imp.get()),
            ),
            osc_settings=OscSettings(
                full_scale_v=float(CvtTools.parse_to_V(vm.osc_range.get())),
                offset_v=float(CvtTools.parse_to_V(vm.osc_offset.get())),
                points=max(2, _safe_int(vm.osc_points.get(), 10_000)),
                impedance=ImpedanceMode(vm.osc_imp.get()),
                coupling=CouplingMode(vm.osc_coupling.get()),
            ),
        ),
        magnitude_phase_mode=MagnitudePhaseMode(vm.magnitude_phase_mode.get()),
        auto_save_data=bool(vm.auto_save_data.get()),
    )



def settings_to_vm(settings: AppSettings, vm: ViewModel) -> None:
    vm.freq_unit.set(settings.freq_unit)

    scale = CvtTools.convert_general_unit(settings.freq_unit)
    vm.start_freq.set(str(round(settings.sweep.start_hz / scale, 6)))
    vm.stop_freq.set(str(round(settings.sweep.stop_hz / scale, 6)))
    if settings.sweep.step_hz is not None:
        vm.step_freq.set(str(round(settings.sweep.step_hz / scale, 6)))
    vm.step_count.set(str(settings.sweep.step_count or 100))
    vm.is_log.set(settings.sweep.is_log)

    vm.awg_model.set(settings.setup.awg.model)
    vm.osc_model.set(settings.setup.osc.model)
    vm.awg_connect_mode.set(settings.setup.awg.connect_mode.value)
    vm.osc_connect_mode.set(settings.setup.osc.connect_mode.value)
    vm.awg_visa.set(settings.setup.awg.visa_address)
    vm.osc_visa.set(settings.setup.osc.visa_address)
    vm.awg_ip.set(settings.setup.awg.ip_address)
    vm.osc_ip.set(settings.setup.osc.ip_address)

    vm.awg_amp.set(str(settings.setup.awg_settings.amplitude_vpp))
    vm.awg_imp.set(settings.setup.awg_settings.impedance.value)

    vm.osc_range.set(str(settings.setup.osc_settings.full_scale_v))
    vm.osc_offset.set(str(settings.setup.osc_settings.offset_v))
    vm.osc_points.set(str(settings.setup.osc_settings.points))
    vm.osc_imp.set(settings.setup.osc_settings.impedance.value)
    vm.osc_coupling.set(settings.setup.osc_settings.coupling.value)

    vm.awg_ch.set(str(settings.setup.channels.awg_ch))
    vm.osc_test_ch.set(str(settings.setup.channels.osc_test_ch))
    vm.osc_ref_ch.set(str(settings.setup.channels.osc_ref_ch or 2))
    vm.osc_trig_ch.set(str(settings.setup.channels.osc_trig_ch or 2))

    vm.correction_mode.set(settings.run_mode.correction_mode.value)
    vm.trigger_mode.set(settings.run_mode.trigger_mode.value)
    vm.auto_range.set(settings.run_mode.auto_range)
    vm.auto_reset.set(settings.run_mode.auto_reset)

    vm.magnitude_phase_mode.set(settings.magnitude_phase_mode.value)
    vm.auto_save_data.set(settings.auto_save_data)
