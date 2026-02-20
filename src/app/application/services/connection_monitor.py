from __future__ import annotations

import threading
import time
from collections.abc import Callable

from app.application.events import ConnectionStatusUpdated, EventEmitter
from app.infrastructure.instruments.ports import ResourceScannerPort


class ConnectionMonitor:
    def __init__(
        self,
        scanner: ResourceScannerPort,
        get_awg_address: Callable[[], str],
        get_osc_address: Callable[[], str],
        emitter: EventEmitter,
        interval_s: float = 0.5,
    ) -> None:
        self._scanner = scanner
        self._get_awg_address = get_awg_address
        self._get_osc_address = get_osc_address
        self._emitter = emitter
        self._interval_s = interval_s
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            awg_connected = False
            osc_connected = False
            try:
                resources = self._scanner.list_resources()
                awg_connected = self._get_awg_address() in resources if self._get_awg_address() else False
                osc_connected = self._get_osc_address() in resources if self._get_osc_address() else False
            except Exception:
                awg_connected = False
                osc_connected = False

            self._emitter.emit(
                ConnectionStatusUpdated(awg_connected=awg_connected, osc_connected=osc_connected)
            )
            time.sleep(self._interval_s)
