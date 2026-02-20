from __future__ import annotations

class PyVisaResourceScanner:
    def __init__(self) -> None:
        self._rm = None

    def list_resources(self) -> tuple[str, ...]:
        try:
            import pyvisa as visa
        except ModuleNotFoundError:
            return tuple()

        if self._rm is None:
            self._rm = visa.ResourceManager()
        try:
            return tuple(self._rm.list_resources())
        except Exception:
            self._rm = visa.ResourceManager()
            return tuple(self._rm.list_resources())
