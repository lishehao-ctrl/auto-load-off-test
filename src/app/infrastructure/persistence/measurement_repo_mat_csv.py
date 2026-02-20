from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.io import loadmat, savemat

from app.application.dto import LoadedMeasurement, SaveArtifacts, SaveTarget
from app.domain.exporters import result_to_arrays, settings_to_metadata
from app.domain.models import AppSettings, SweepPoint, SweepResult


class MatCsvMeasurementRepository:
    def save(self, result: SweepResult, settings: AppSettings, target: SaveTarget) -> SaveArtifacts:
        directory = target.base_path.parent
        directory.mkdir(parents=True, exist_ok=True)

        stem = target.base_path.stem if target.base_path.suffix else target.base_path.name
        prefix = datetime.now().strftime("%Y%m%d_%H_%M_%S_") if target.include_timestamp else ""
        file_base = f"{prefix}{stem}"

        mat_path = directory / f"{file_base}.mat"
        csv_path = directory / f"{file_base}.csv"
        txt_path = directory / f"{file_base}.txt"

        arrays = result_to_arrays(result)
        payload: dict[str, object] = {
            "schema_version": settings.schema_version,
            "metadata_json": json.dumps(settings_to_metadata(settings), ensure_ascii=True),
        }
        payload.update(arrays)
        savemat(mat_path, payload)

        freq = arrays.get("freq_hz", np.array([], dtype=float))
        gain_linear = arrays.get("gain_linear", np.array([], dtype=float))
        gain_db = arrays.get("gain_db", np.array([], dtype=float))
        phase = arrays.get("phase_deg", np.array([], dtype=float))

        headers = ["freq_hz", "gain_linear", "gain_db", "phase_deg"]
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for idx in range(len(freq)):
                writer.writerow(
                    [
                        float(freq[idx]),
                        float(gain_linear[idx]) if idx < len(gain_linear) else "",
                        float(gain_db[idx]) if idx < len(gain_db) else "",
                        float(phase[idx]) if idx < len(phase) else "",
                    ]
                )

        rows = np.column_stack(
            [
                freq,
                gain_linear if len(gain_linear) == len(freq) else np.full(len(freq), np.nan),
                gain_db if len(gain_db) == len(freq) else np.full(len(freq), np.nan),
                phase if len(phase) == len(freq) else np.full(len(freq), np.nan),
            ]
        )
        np.savetxt(txt_path, rows, delimiter="\t", header="\t".join(headers), comments="")

        gain_plot_path = None
        db_plot_path = None

        gain_fig = target.figures.get("gain")
        db_fig = target.figures.get("db")

        if gain_fig is not None:
            gain_plot_path = directory / f"{file_base}_gain.png"
            gain_fig.savefig(gain_plot_path, dpi=300)
        if db_fig is not None:
            db_plot_path = directory / f"{file_base}_gain_db.png"
            db_fig.savefig(db_plot_path, dpi=300)

        return SaveArtifacts(
            mat_path=mat_path,
            csv_path=csv_path,
            txt_path=txt_path,
            gain_plot_path=gain_plot_path,
            db_plot_path=db_plot_path,
        )

    def load(self, file_path: str) -> LoadedMeasurement:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".mat":
            payload = loadmat(path)
            freq = self._get_array(payload, ["freq_hz", "freq"])  # type: ignore[arg-type]
            gain_linear = self._get_array(payload, ["gain_linear", "gain_raw"])
            gain_db = self._get_array(payload, ["gain_db", "gain_db_raw", "gain_db_corr"])
            phase = self._get_array(payload, ["phase_deg", "phase", "phase_deg_corr"], required=False)

        elif suffix == ".csv":
            freq_l: list[float] = []
            gain_l: list[float] = []
            gain_db_l: list[float] = []
            phase_l: list[float] = []
            with path.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    freq_l.append(float(row.get("freq_hz", "0") or 0.0))
                    gain_l.append(float(row.get("gain_linear", "0") or 0.0))
                    gain_db_l.append(float(row.get("gain_db", "0") or 0.0))
                    if row.get("phase_deg") not in (None, ""):
                        phase_l.append(float(row["phase_deg"]))
            freq = np.array(freq_l, dtype=float)
            gain_linear = np.array(gain_l, dtype=float)
            gain_db = np.array(gain_db_l, dtype=float)
            phase = np.array(phase_l, dtype=float) if phase_l else None
            payload = {"freq_hz": freq, "gain_linear": gain_linear, "gain_db": gain_db}
            if phase is not None:
                payload["phase_deg"] = phase

        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        points: list[SweepPoint] = []
        n = len(freq)
        for idx in range(n):
            phase_deg = float(phase[idx]) if phase is not None and idx < len(phase) else None
            points.append(
                SweepPoint(
                    freq_hz=float(freq[idx]),
                    gain_linear=float(gain_linear[idx]) if idx < len(gain_linear) else 0.0,
                    gain_db=float(gain_db[idx]) if idx < len(gain_db) else 0.0,
                    phase_deg=phase_deg,
                    gain_complex=(
                        complex(
                            float(gain_linear[idx]) * np.cos(np.deg2rad(phase_deg)),
                            float(gain_linear[idx]) * np.sin(np.deg2rad(phase_deg)),
                        )
                        if phase_deg is not None and idx < len(gain_linear)
                        else None
                    ),
                )
            )

        return LoadedMeasurement(result=SweepResult(points=points), raw_payload=payload)

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
