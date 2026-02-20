from __future__ import annotations

import queue
import threading
from pathlib import Path

from app.application.dto import SaveTarget, StartSweepCommand
from app.application.events import (
    ConnectionStatusUpdated,
    SweepCompleted,
    SweepDataUpdated,
    SweepFailed,
    SweepProgress,
    SweepStarted,
    SweepStopped,
    SweepWarning,
)
from app.application.services.connection_monitor import ConnectionMonitor
from app.application.use_cases.load_measurement import LoadMeasurementUseCase
from app.application.use_cases.load_reference import LoadReferenceUseCase
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.application.use_cases.settings_use_case import SettingsUseCase
from app.application.use_cases.start_sweep import StartSweepUseCase
from app.application.use_cases.stop_sweep import StopSweepUseCase
from app.domain.models import AppSettings, SweepResult
from app.infrastructure.instruments.equips_factory import create_instrument_ports, resolve_visa_address
from app.infrastructure.instruments.ports import ResourceScannerPort
from app.presentation.tk import dialogs
from app.presentation.tk.app_window import AppWindow
from app.presentation.tk.mapper import settings_to_vm, vm_to_settings
from app.presentation.tk.view_model import ViewModel


class TkController:
    def __init__(
        self,
        *,
        window: AppWindow,
        vm: ViewModel,
        settings_use_case: SettingsUseCase,
        save_measurement_use_case: SaveMeasurementUseCase,
        load_measurement_use_case: LoadMeasurementUseCase,
        load_reference_use_case: LoadReferenceUseCase,
        scanner: ResourceScannerPort,
    ) -> None:
        self.window = window
        self.vm = vm

        self.settings_use_case = settings_use_case
        self.save_measurement_use_case = save_measurement_use_case
        self.load_measurement_use_case = load_measurement_use_case
        self.load_reference_use_case = load_reference_use_case

        self._event_queue: queue.Queue[object] = queue.Queue()
        self._latest_result = SweepResult()
        self._reference_interpolator = None

        self._ports = None
        self._sweep_thread: threading.Thread | None = None
        self._stop_use_case: StopSweepUseCase | None = None

        self._root_dir = Path(__file__).resolve().parents[4]
        self._monitor = ConnectionMonitor(
            scanner=scanner,
            get_awg_address=self._get_awg_target_address,
            get_osc_address=self._get_osc_target_address,
            emitter=self,
        )

    def initialize(self) -> None:
        self.window.bind_actions(
            on_start=self.on_start,
            on_stop=self.on_stop,
            on_save_data=self.on_save_data,
            on_load_data=self.on_load_data,
            on_load_ref=self.on_load_reference,
            on_save_settings=self.on_save_settings,
            on_load_settings=self.on_load_settings,
            on_close=self.on_close,
            on_figure_change=self.on_figure_change,
            on_mag_phase_change=self.on_mag_phase_change,
        )

        try:
            settings = self.settings_use_case.load()
            settings_to_vm(settings, self.vm)
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load settings: {exc}")

        self._monitor.start()
        self.window.after(100, self._process_events)
        self.on_figure_change()
        self.on_mag_phase_change()

    def emit(self, event: object) -> None:
        self._event_queue.put(event)

    def on_start(self) -> None:
        if self._sweep_thread and self._sweep_thread.is_alive():
            return

        try:
            settings = vm_to_settings(self.vm)
            ports = create_instrument_ports(settings.setup)
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Invalid settings: {exc}")
            return

        stop_event = threading.Event()
        self._stop_use_case = StopSweepUseCase(stop_event=stop_event)

        cmd = StartSweepCommand(
            settings=settings,
            calibration_enabled=bool(self.vm.calibration_enabled.get()),
            reference_interpolator=self._reference_interpolator,
        )

        self._ports = ports
        start_use_case = StartSweepUseCase(awg=ports.awg, osc=ports.osc, stop_event=stop_event)

        self.window.btn_start.configure(state="disabled")
        self.window.btn_stop.configure(state="normal")
        self.vm.status_text.set("Sweep started")

        self._sweep_thread = threading.Thread(target=self._run_sweep, args=(start_use_case, cmd), daemon=True)
        self._sweep_thread.start()

    def on_stop(self) -> None:
        if self._stop_use_case is not None:
            self._stop_use_case.stop()

    def on_save_settings(self) -> None:
        try:
            settings = vm_to_settings(self.vm)
            self.settings_use_case.save(settings)
            dialogs.show_info(self.window, "Settings saved")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to save settings: {exc}")

    def on_load_settings(self) -> None:
        try:
            settings = self.settings_use_case.load()
            settings_to_vm(settings, self.vm)
            self.on_figure_change()
            self.on_mag_phase_change()
            dialogs.show_info(self.window, "Settings loaded")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load settings: {exc}")

    def on_save_data(self) -> None:
        if self._latest_result.is_empty:
            dialogs.show_warning(self.window, "No measurement data available")
            return

        fp = dialogs.ask_save_file(
            title="Save measurement",
            initial_dir=self._root_dir / "__data__",
            initial_name="measurement",
            filetypes=[("All files", "*.*")],
        )
        if fp is None:
            return

        try:
            settings = vm_to_settings(self.vm)
            artifacts = self.save_measurement_use_case.execute(
                result=self._latest_result,
                settings=settings,
                target=SaveTarget(base_path=fp, include_timestamp=False, figures=self.window.plot_widget.figures()),
            )
            dialogs.show_info(self.window, f"Saved: {artifacts.mat_path.name}")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to save data: {exc}")

    def on_load_data(self) -> None:
        fp = dialogs.ask_open_file(
            title="Load measurement",
            initial_dir=self._root_dir / "__data__",
            filetypes=[("Measurement", "*.mat *.csv"), ("All files", "*.*")],
        )
        if fp is None:
            return

        try:
            loaded = self.load_measurement_use_case.execute(str(fp))
            self._latest_result = loaded.result
            self.window.plot_widget.update_result(
                self._latest_result,
                self.vm.freq_unit.get(),
                self.vm.magnitude_phase_mode.get(),
            )
            dialogs.show_info(self.window, "Measurement loaded")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load data: {exc}")

    def on_load_reference(self) -> None:
        fp = dialogs.ask_open_file(
            title="Load reference",
            initial_dir=self._root_dir / "__data__",
            filetypes=[("MAT files", "*.mat"), ("All files", "*.*")],
        )
        if fp is None:
            return

        try:
            _curve, interpolator = self.load_reference_use_case.execute(str(fp))
            self._reference_interpolator = interpolator
            self.vm.calibration_enabled.set(True)
            dialogs.show_info(self.window, "Reference loaded")
        except Exception as exc:  # noqa: BLE001
            dialogs.show_warning(self.window, f"Failed to load reference: {exc}")

    def on_figure_change(self) -> None:
        self.window.plot_widget.set_mode(self.vm.figure_mode.get())

    def on_mag_phase_change(self) -> None:
        self.window.plot_widget.update_result(
            self._latest_result,
            self.vm.freq_unit.get(),
            self.vm.magnitude_phase_mode.get(),
        )

    def on_close(self) -> None:
        self._monitor.stop()
        if self._stop_use_case is not None:
            self._stop_use_case.stop()

        try:
            settings = vm_to_settings(self.vm)
            self.settings_use_case.save(settings)
        except Exception:
            pass

        self._close_ports()
        self.window.destroy()

    def _run_sweep(self, start_use_case: StartSweepUseCase, cmd: StartSweepCommand) -> None:
        try:
            result = start_use_case.run(cmd, self)
            if not result.is_empty:
                self._latest_result = result

                if self.vm.auto_save_data.get():
                    settings = cmd.settings
                    target = SaveTarget(
                        base_path=self._root_dir / "__data__" / "measurement",
                        include_timestamp=True,
                        figures={},
                    )
                    self.save_measurement_use_case.execute(result=result, settings=settings, target=target)
        except Exception as exc:  # noqa: BLE001
            self.emit(SweepFailed(error_code="SWEEP_THREAD", message=str(exc)))
        finally:
            self._close_ports()

    def _close_ports(self) -> None:
        if self._ports is None:
            return
        try:
            self._ports.awg.close()
        except Exception:
            pass
        try:
            self._ports.osc.close()
        except Exception:
            pass
        self._ports = None

    def _process_events(self) -> None:
        try:
            while True:
                event = self._event_queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        finally:
            self.window.after(100, self._process_events)

    def _handle_event(self, event: object) -> None:
        if isinstance(event, ConnectionStatusUpdated):
            self.window.set_connection_status(event.awg_connected, event.osc_connected)
            return

        if isinstance(event, SweepStarted):
            self.vm.status_text.set(f"Sweep started ({event.total_points} points)")
            return

        if isinstance(event, SweepProgress):
            self.vm.status_text.set(
                f"Freq {event.freq_hz:.2f} Hz ({event.point_index}/{event.total_points})"
            )
            return

        if isinstance(event, SweepDataUpdated):
            self._latest_result = event.partial_result
            self.window.plot_widget.update_result(
                self._latest_result,
                self.vm.freq_unit.get(),
                self.vm.magnitude_phase_mode.get(),
            )
            return

        if isinstance(event, SweepWarning):
            if event.code in {"READY", "FREQ_MISMATCH", "AMP_MISMATCH"}:
                self.vm.status_text.set(event.message)
            else:
                dialogs.show_warning(self.window, event.message)
            return

        if isinstance(event, SweepFailed):
            self.vm.status_text.set(f"Sweep failed: {event.message}")
            self.window.btn_start.configure(state="normal")
            self.window.btn_stop.configure(state="disabled")
            dialogs.show_warning(self.window, event.message)
            return

        if isinstance(event, SweepStopped):
            self._latest_result = event.result
            self.vm.status_text.set("Sweep stopped")
            self.window.btn_start.configure(state="normal")
            self.window.btn_stop.configure(state="disabled")
            return

        if isinstance(event, SweepCompleted):
            self._latest_result = event.result
            self.vm.status_text.set("Sweep completed")
            self.window.plot_widget.update_result(
                self._latest_result,
                self.vm.freq_unit.get(),
                self.vm.magnitude_phase_mode.get(),
            )
            self.window.btn_start.configure(state="normal")
            self.window.btn_stop.configure(state="disabled")
            return

    def _get_awg_target_address(self) -> str:
        try:
            settings = vm_to_settings(self.vm)
            return resolve_visa_address(settings.setup.awg)
        except Exception:
            return ""

    def _get_osc_target_address(self) -> str:
        try:
            settings = vm_to_settings(self.vm)
            return resolve_visa_address(settings.setup.osc)
        except Exception:
            return ""
