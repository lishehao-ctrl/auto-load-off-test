from __future__ import annotations

import numpy as np
from scipy.io import loadmat

from app.domain.models import ReferenceCurve


class MatReferenceRepository:
    def load_reference(self, file_path: str) -> ReferenceCurve:
        payload = loadmat(file_path)

        freq = self._get_array(payload, ["freq_hz", "freq"])
        gain_db = self._get_array(payload, ["gain_db", "gain_db_raw", "gain_db_corr"])
        phase = self._get_array(payload, ["phase_deg", "phase", "phase_deg_corr"], required=False)

        return ReferenceCurve(freq_hz=freq, gain_db=gain_db, phase_deg=phase)

    def _get_array(
        self,
        payload: dict[str, np.ndarray],
        keys: list[str],
        *,
        required: bool = True,
    ) -> np.ndarray | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, np.ndarray):
                return np.asarray(value, dtype=float).squeeze()
        if required:
            raise ValueError(f"Missing required keys: {keys}")
        return None
