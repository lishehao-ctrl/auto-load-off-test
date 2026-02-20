from __future__ import annotations


class ApplicationError(Exception):
    pass


class ValidationAppError(ApplicationError):
    pass


class InstrumentAppError(ApplicationError):
    pass


class PersistenceAppError(ApplicationError):
    pass
