from __future__ import annotations

from dataclasses import asdict

import numpy as np

from app.domain.models import AppSettings, SweepResult


def result_to_arrays(result: SweepResult) -> dict[str, np.ndarray]:
    freq = np.array([p.freq_hz for p in result.points], dtype=float)
    gain = np.array([p.gain_linear for p in result.points], dtype=float)
    gain_db = np.array([p.gain_db for p in result.points], dtype=float)

    phase_values = [p.phase_deg for p in result.points if p.phase_deg is not None]
    complex_values = [p.gain_complex for p in result.points if p.gain_complex is not None]

    arrays: dict[str, np.ndarray] = {
        "freq_hz": freq,
        "gain_linear": gain,
        "gain_db": gain_db,
    }

    if phase_values:
        arrays["phase_deg"] = np.array(phase_values, dtype=float)
    if complex_values:
        arrays["gain_complex_real"] = np.array([v.real for v in complex_values], dtype=float)
        arrays["gain_complex_imag"] = np.array([v.imag for v in complex_values], dtype=float)
    return arrays


def settings_to_metadata(settings: AppSettings) -> dict[str, object]:
    data = asdict(settings)
    return {
        "schema_version": data["schema_version"],
        "freq_unit": data["freq_unit"],
        "sweep": data["sweep"],
        "run_mode": data["run_mode"],
        "setup": data["setup"],
        "magnitude_phase_mode": data["magnitude_phase_mode"],
    }
