from __future__ import annotations

from typing import Protocol

from app.application.dto import LoadedMeasurement, SaveArtifacts, SaveTarget
from app.domain.models import AppSettings, ReferenceCurve, SweepResult


class SettingsRepository(Protocol):
    def load(self) -> AppSettings: ...
    def save(self, settings: AppSettings) -> None: ...


class MeasurementRepository(Protocol):
    def save(self, result: SweepResult, settings: AppSettings, target: SaveTarget) -> SaveArtifacts: ...
    def load(self, file_path: str) -> LoadedMeasurement: ...


class ReferenceRepository(Protocol):
    def load_reference(self, file_path: str) -> ReferenceCurve: ...
