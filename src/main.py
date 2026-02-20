from __future__ import annotations

from app.application.use_cases.load_measurement import LoadMeasurementUseCase
from app.application.use_cases.load_reference import LoadReferenceUseCase
from app.application.use_cases.save_measurement import SaveMeasurementUseCase
from app.application.use_cases.settings_use_case import SettingsUseCase
from app.infrastructure.instruments.resource_scanner import PyVisaResourceScanner
from app.infrastructure.persistence.measurement_repo_mat_csv import MatCsvMeasurementRepository
from app.infrastructure.persistence.reference_repo_mat import MatReferenceRepository
from app.infrastructure.persistence.settings_repo_json import JsonSettingsRepository
from app.presentation.tk.app_window import AppWindow
from app.presentation.tk.controller import TkController


def main() -> None:
    window = AppWindow()
    vm = window.vm

    settings_repo = JsonSettingsRepository()
    measurement_repo = MatCsvMeasurementRepository()
    reference_repo = MatReferenceRepository()

    controller = TkController(
        window=window,
        vm=vm,
        settings_use_case=SettingsUseCase(settings_repo),
        save_measurement_use_case=SaveMeasurementUseCase(measurement_repo),
        load_measurement_use_case=LoadMeasurementUseCase(measurement_repo),
        load_reference_use_case=LoadReferenceUseCase(reference_repo),
        scanner=PyVisaResourceScanner(),
    )
    controller.initialize()

    window.mainloop()


if __name__ == "__main__":
    main()
