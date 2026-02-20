from __future__ import annotations

import numpy as np

from app.domain.models import SweepSpec


def generate_frequency_points(spec: SweepSpec) -> np.ndarray:
    if spec.is_log:
        step_count = max(1, int(spec.step_count or 1))
        return np.logspace(np.log10(spec.start_hz), np.log10(spec.stop_hz), step_count)

    step_hz = float(spec.step_hz or 0.0)
    if step_hz <= 0:
        raise ValueError("Linear sweep requires step_hz > 0")

    if np.isclose(spec.start_hz, spec.stop_hz):
        return np.array([spec.start_hz], dtype=float)

    values: list[float] = []
    current = spec.start_hz
    while spec.stop_hz - current >= -1e-9:
        values.append(current)
        current += step_hz

    if not values:
        values = [spec.start_hz]
    return np.array(values, dtype=float)


def compute_sampling_window_s(
    freq_hz: float,
    sample_rate_hz: float,
    points: int,
    *,
    min_window_s: float = 1e-6,
    min_cycles: int = 10,
    max_points: int = 10_000_000,
) -> float:
    freq = max(float(freq_hz), 1e-12)
    sr = max(float(sample_rate_hz), 1.0)
    target = max(points / sr, min_cycles / freq, min_window_s)
    if max_points > 0:
        target = min(target, max_points / sr)
    return target
