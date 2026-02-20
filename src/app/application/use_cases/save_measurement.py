from __future__ import annotations

from app.application.dto import SaveArtifacts, SaveTarget
from app.domain.models import AppSettings, SweepResult
from app.infrastructure.persistence.repository_ports import MeasurementRepository


class SaveMeasurementUseCase:
    def __init__(self, repository: MeasurementRepository) -> None:
        self._repository = repository

    def execute(self, result: SweepResult, settings: AppSettings, target: SaveTarget) -> SaveArtifacts:
        return self._repository.save(result=result, settings=settings, target=target)
