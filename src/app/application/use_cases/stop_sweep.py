from __future__ import annotations

import threading


class StopSweepUseCase:
    def __init__(self, stop_event: threading.Event) -> None:
        self._stop_event = stop_event

    def stop(self) -> None:
        self._stop_event.set()

    def clear(self) -> None:
        self._stop_event.clear()

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event
