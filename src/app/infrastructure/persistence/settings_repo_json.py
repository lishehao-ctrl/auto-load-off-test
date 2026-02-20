from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from mapping import Mapping

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
from app.domain.validators import validate_settings


class JsonSettingsRepository:
    def __init__(self, config_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[4]
        default_path = root / "__config__" / "settings.json"
        self._path = config_path or default_path

    def load(self) -> AppSettings:
        if not self._path.exists():
            settings = self._default_settings()
            self.save(settings)
            return settings

        payload = json.loads(self._path.read_text(encoding="utf-8"))
        settings = self._from_dict(payload)
        validate_settings(settings)
        return settings

    def save(self, settings: AppSettings) -> None:
        validate_settings(settings)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = self._to_dict(settings)
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")

    def _default_settings(self) -> AppSettings:
        return AppSettings(
            schema_version=1,
            freq_unit=Mapping.mapping_mhz,
            sweep=SweepSpec(
                start_hz=1e6,
                stop_hz=100e6,
                step_hz=1e6,
                step_count=100,
                is_log=False,
            ),
            run_mode=RunMode(
                correction_mode=CorrectionMode.NONE,
                trigger_mode=TriggerMode.FREE_RUN,
                auto_range=True,
                auto_reset=True,
            ),
            setup=InstrumentSetup(
                awg=InstrumentEndpoint(
                    model=Mapping.mapping_DSG_4102,
                    connect_mode=ConnectionMode.AUTO,
                    visa_address="",
                    ip_address="0.0.0.0",
                ),
                osc=InstrumentEndpoint(
                    model=Mapping.mapping_MDO_34,
                    connect_mode=ConnectionMode.AUTO,
                    visa_address="",
                    ip_address="0.0.0.0",
                ),
                channels=ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=2, osc_trig_ch=2),
                awg_settings=AwgSettings(amplitude_vpp=1.0, impedance=ImpedanceMode.R50),
                osc_settings=OscSettings(
                    full_scale_v=1.0,
                    offset_v=0.0,
                    points=10_000,
                    impedance=ImpedanceMode.R50,
                    coupling=CouplingMode.DC,
                ),
            ),
            magnitude_phase_mode=MagnitudePhaseMode.MAG,
            auto_save_data=True,
        )

    def _to_dict(self, settings: AppSettings) -> dict[str, object]:
        payload = asdict(settings)
        payload["run_mode"]["correction_mode"] = settings.run_mode.correction_mode.value
        payload["run_mode"]["trigger_mode"] = settings.run_mode.trigger_mode.value
        payload["setup"]["awg"]["connect_mode"] = settings.setup.awg.connect_mode.value
        payload["setup"]["osc"]["connect_mode"] = settings.setup.osc.connect_mode.value
        payload["setup"]["awg_settings"]["impedance"] = settings.setup.awg_settings.impedance.value
        payload["setup"]["osc_settings"]["impedance"] = settings.setup.osc_settings.impedance.value
        payload["setup"]["osc_settings"]["coupling"] = settings.setup.osc_settings.coupling.value
        payload["magnitude_phase_mode"] = settings.magnitude_phase_mode.value
        return payload

    def _from_dict(self, payload: dict[str, object]) -> AppSettings:
        sweep_payload = payload.get("sweep", {})
        run_payload = payload.get("run_mode", {})
        setup_payload = payload.get("setup", {})

        awg_payload = setup_payload.get("awg", {}) if isinstance(setup_payload, dict) else {}
        osc_payload = setup_payload.get("osc", {}) if isinstance(setup_payload, dict) else {}
        channels_payload = setup_payload.get("channels", {}) if isinstance(setup_payload, dict) else {}
        awg_settings_payload = setup_payload.get("awg_settings", {}) if isinstance(setup_payload, dict) else {}
        osc_settings_payload = setup_payload.get("osc_settings", {}) if isinstance(setup_payload, dict) else {}

        return AppSettings(
            schema_version=int(payload.get("schema_version", 1)),
            freq_unit=str(payload.get("freq_unit", Mapping.mapping_mhz)),
            sweep=SweepSpec(
                start_hz=float(sweep_payload.get("start_hz", 1e6)),
                stop_hz=float(sweep_payload.get("stop_hz", 100e6)),
                step_hz=(
                    None
                    if sweep_payload.get("step_hz") is None
                    else float(sweep_payload.get("step_hz", 1e6))
                ),
                step_count=(
                    None
                    if sweep_payload.get("step_count") is None
                    else int(sweep_payload.get("step_count", 100))
                ),
                is_log=bool(sweep_payload.get("is_log", False)),
            ),
            run_mode=RunMode(
                correction_mode=CorrectionMode(str(run_payload.get("correction_mode", CorrectionMode.NONE.value))),
                trigger_mode=TriggerMode(str(run_payload.get("trigger_mode", TriggerMode.FREE_RUN.value))),
                auto_range=bool(run_payload.get("auto_range", True)),
                auto_reset=bool(run_payload.get("auto_reset", True)),
            ),
            setup=InstrumentSetup(
                awg=InstrumentEndpoint(
                    model=str(awg_payload.get("model", Mapping.mapping_DSG_4102)),
                    connect_mode=ConnectionMode(str(awg_payload.get("connect_mode", ConnectionMode.AUTO.value))),
                    visa_address=str(awg_payload.get("visa_address", "")),
                    ip_address=str(awg_payload.get("ip_address", "0.0.0.0")),
                ),
                osc=InstrumentEndpoint(
                    model=str(osc_payload.get("model", Mapping.mapping_MDO_34)),
                    connect_mode=ConnectionMode(str(osc_payload.get("connect_mode", ConnectionMode.AUTO.value))),
                    visa_address=str(osc_payload.get("visa_address", "")),
                    ip_address=str(osc_payload.get("ip_address", "0.0.0.0")),
                ),
                channels=ChannelSelection(
                    awg_ch=int(channels_payload.get("awg_ch", 1)),
                    osc_test_ch=int(channels_payload.get("osc_test_ch", 1)),
                    osc_ref_ch=(
                        None
                        if channels_payload.get("osc_ref_ch") is None
                        else int(channels_payload.get("osc_ref_ch"))
                    ),
                    osc_trig_ch=(
                        None
                        if channels_payload.get("osc_trig_ch") is None
                        else int(channels_payload.get("osc_trig_ch"))
                    ),
                ),
                awg_settings=AwgSettings(
                    amplitude_vpp=float(awg_settings_payload.get("amplitude_vpp", 1.0)),
                    impedance=ImpedanceMode(str(awg_settings_payload.get("impedance", ImpedanceMode.R50.value))),
                ),
                osc_settings=OscSettings(
                    full_scale_v=float(osc_settings_payload.get("full_scale_v", 1.0)),
                    offset_v=float(osc_settings_payload.get("offset_v", 0.0)),
                    points=int(osc_settings_payload.get("points", 10_000)),
                    impedance=ImpedanceMode(str(osc_settings_payload.get("impedance", ImpedanceMode.R50.value))),
                    coupling=CouplingMode(str(osc_settings_payload.get("coupling", CouplingMode.DC.value))),
                ),
            ),
            magnitude_phase_mode=MagnitudePhaseMode(
                str(payload.get("magnitude_phase_mode", MagnitudePhaseMode.MAG.value))
            ),
            auto_save_data=bool(payload.get("auto_save_data", True)),
        )
