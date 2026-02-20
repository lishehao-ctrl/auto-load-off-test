from __future__ import annotations

from collections.abc import Callable

import numpy as np
from scipy.interpolate import make_interp_spline

from app.domain.models import ReferenceCurve, SweepPoint


def build_reference_interpolator(curve: ReferenceCurve) -> Callable[[np.ndarray], np.ndarray]:
    freq = np.asarray(curve.freq_hz, dtype=float).squeeze()
    gain_db = np.asarray(curve.gain_db, dtype=float).squeeze()
    phase = None if curve.phase_deg is None else np.asarray(curve.phase_deg, dtype=float).squeeze()

    if freq.size == 0:
        raise ValueError("Reference frequency data is empty")

    if phase is None or phase.size == 0:
        href = 10 ** (gain_db / 20.0)
    else:
        href = 10 ** (gain_db / 20.0) * np.exp(1j * np.deg2rad(phase))

    order = np.argsort(freq)
    freq = freq[order]
    href = href[order]

    freq, unique_idx = np.unique(freq, return_index=True)
    href = href[unique_idx]

    if freq.size == 1:
        h0 = href[0]

        def constant_interp(xs: np.ndarray) -> np.ndarray:
            x = np.asarray(xs, dtype=float)
            out = np.empty_like(x, dtype=np.complex128 if np.iscomplexobj(h0) else float)
            out[...] = h0
            return out

        return constant_interp

    spline_order = int(min(3, freq.size - 1))
    if np.iscomplexobj(href):
        spline_real = make_interp_spline(freq, href.real, k=spline_order)
        spline_imag = make_interp_spline(freq, href.imag, k=spline_order)

        def complex_interp(xs: np.ndarray) -> np.ndarray:
            x = np.asarray(xs, dtype=float)
            y = np.empty_like(x, dtype=np.complex128)
            lo = x < freq[0]
            hi = x > freq[-1]
            mid = ~(lo | hi)
            if np.any(mid):
                y[mid] = spline_real(x[mid]) + 1j * spline_imag(x[mid])
            if np.any(lo):
                y[lo] = href[0]
            if np.any(hi):
                y[hi] = href[-1]
            return y

        return complex_interp

    spline_mag = make_interp_spline(freq, np.abs(href), k=spline_order)

    def magnitude_interp(xs: np.ndarray) -> np.ndarray:
        x = np.asarray(xs, dtype=float)
        y = np.empty_like(x, dtype=float)
        lo = x < freq[0]
        hi = x > freq[-1]
        mid = ~(lo | hi)
        if np.any(mid):
            y[mid] = spline_mag(x[mid])
        if np.any(lo):
            y[lo] = float(np.abs(href[0]))
        if np.any(hi):
            y[hi] = float(np.abs(href[-1]))
        return y

    return magnitude_interp


def apply_reference_to_point(point: SweepPoint, ref_value: complex | float, use_phase: bool) -> SweepPoint:
    eps = 1e-12
    ref_abs = max(float(np.abs(ref_value)), eps)

    if use_phase:
        if point.gain_complex is not None:
            raw = point.gain_complex
        elif point.phase_deg is not None:
            raw = point.gain_linear * np.exp(1j * np.deg2rad(point.phase_deg))
        else:
            raw = complex(point.gain_linear, 0.0)

        corrected = raw / complex(ref_value)
        gain_linear = float(np.abs(corrected))
        gain_db = float(20.0 * np.log10(max(gain_linear, eps)))
        phase_deg = float(np.degrees(np.angle(corrected)))
        return SweepPoint(
            freq_hz=point.freq_hz,
            gain_linear=gain_linear,
            gain_db=gain_db,
            phase_deg=phase_deg,
            gain_complex=complex(corrected),
        )

    gain_linear = float(point.gain_linear / ref_abs)
    gain_db = float(20.0 * np.log10(max(gain_linear, eps)))
    return SweepPoint(
        freq_hz=point.freq_hz,
        gain_linear=gain_linear,
        gain_db=gain_db,
        phase_deg=point.phase_deg,
        gain_complex=point.gain_complex,
    )
