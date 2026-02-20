from __future__ import annotations

from app.domain.models import AppSettings
from app.infrastructure.persistence.repository_ports import SettingsRepository


class SettingsUseCase:
    def __init__(self, repository: SettingsRepository) -> None:
        self._repository = repository

    def load(self) -> AppSettings:
        return self._repository.load()

    def save(self, settings: AppSettings) -> None:
        self._repository.save(settings)
