from __future__ import annotations

from enum import Enum


class CorrectionMode(str, Enum):
    NONE = "none"
    SINGLE = "single"
    DUAL = "dual"


class TriggerMode(str, Enum):
    FREE_RUN = "free_run"
    TRIGGERED = "triggered"


class ConnectionMode(str, Enum):
    AUTO = "auto"
    LAN = "lan"


class ImpedanceMode(str, Enum):
    R50 = "50"
    HIGH_Z = "INF"


class CouplingMode(str, Enum):
    AC = "AC"
    DC = "DC"


class MagnitudePhaseMode(str, Enum):
    MAG = "magnitude"
    PHASE = "phase"
    MAG_AND_PHASE = "magnitude_phase"
