from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.domain.models import AppSettings, SweepResult


@dataclass(slots=True)
class StartSweepCommand:
    settings: AppSettings
    calibration_enabled: bool = False
    reference_interpolator: Any | None = None


@dataclass(slots=True)
class SaveTarget:
    base_path: Path
    include_timestamp: bool = False
    figures: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SaveArtifacts:
    mat_path: Path
    csv_path: Path
    txt_path: Path
    gain_plot_path: Path | None = None
    db_plot_path: Path | None = None


@dataclass(slots=True)
class LoadedMeasurement:
    result: SweepResult
    raw_payload: dict[str, np.ndarray]
