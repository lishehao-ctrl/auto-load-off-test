from __future__ import annotations

class EquipsAwgAdapter:
    def __init__(self, model: str, visa_address: str) -> None:
        try:
            from equips import inst_mapping
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing runtime dependency: pyvisa/equips is required for instrument access"
            ) from exc

        if model not in inst_mapping:
            raise ValueError(f"Unsupported AWG model: {model}")
        self._inst = inst_mapping[model](name=model, visa_address=visa_address)

    def reset(self) -> None:
        self._inst.rst()

    def output_on(self, channel: int) -> None:
        self._inst.set_on(ch=channel)

    def set_impedance(self, mode: str, channel: int) -> None:
        self._inst.set_imp(imp=mode, ch=channel)

    def set_frequency(self, hz: float, channel: int) -> None:
        self._inst.set_freq(freq=hz, ch=channel)

    def get_frequency(self, channel: int) -> float:
        return float(self._inst.get_freq(ch=channel))

    def set_amplitude_vpp(self, vpp: float, channel: int) -> None:
        self._inst.set_amp(amp=vpp, ch=channel)

    def get_amplitude_vpp(self, channel: int) -> float:
        return float(self._inst.get_amp(ch=channel))

    def close(self) -> None:
        try:
            self._inst.inst_close()
        except Exception:
            pass
