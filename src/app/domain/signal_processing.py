from __future__ import annotations

import math

import numpy as np


def calc_vin_peak(vpp_panel: float, awg_impedance: str, osc_impedance: str) -> float:
    source_r = 50.0
    load_r = 50.0 if str(osc_impedance) == "50" else 1e6

    # AWG panel voltage is specified at matched load for 50-ohm output.
    voc = 2.0 * vpp_panel if str(awg_impedance) == "50" else vpp_panel
    vload = voc * load_r / (source_r + load_r)
    return 0.5 * vload


def _parabolic_interp_delta(m1: float, m0: float, p1: float) -> float:
    eps = 1e-30
    m1_ln = np.log(max(m1, eps))
    m0_ln = np.log(max(m0, eps))
    p1_ln = np.log(max(p1, eps))
    denominator = m1_ln - 2.0 * m0_ln + p1_ln
    if abs(denominator) < 1e-12:
        return 0.0
    return 0.5 * (m1_ln - p1_ln) / denominator


def _complex_tone_at(times: np.ndarray, volts_ac: np.ndarray, f_hz: float, window: np.ndarray) -> complex:
    return np.sum(window * volts_ac * np.exp(-1j * 2.0 * np.pi * f_hz * times))


def _windowed_fft(times: np.ndarray, volts: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int, int]:
    volts_ac = volts - np.mean(volts)
    window = np.hanning(len(volts_ac))
    fft_values = np.fft.rfft(window * volts_ac)
    return volts_ac, window, fft_values, len(volts_ac), 0, len(fft_values)


def _tone_metrics(times: np.ndarray, volts: np.ndarray, target_hz: float) -> tuple[float, float, complex, np.ndarray, int, int]:
    volts_ac = volts - np.mean(volts)
    window = np.hanning(len(volts_ac))
    spectrum = np.fft.rfft(window * volts_ac)
    freqs = np.fft.rfftfreq(len(volts_ac), times[1] - times[0])

    k0 = int(np.argmin(np.abs(freqs - target_hz)))
    lo = max(0, k0 - 2)
    hi = min(len(spectrum), k0 + 3)

    band_energy = np.sum(np.abs(spectrum[lo:hi]) ** 2)
    amplitude_peak = (2.0 / np.sqrt(np.sum(window**2) * len(volts_ac))) * np.sqrt(max(band_energy, 1e-30))

    mags = np.abs(spectrum)
    if 1 <= k0 <= mags.size - 2:
        delta = _parabolic_interp_delta(mags[k0 - 1], mags[k0], mags[k0 + 1])
    else:
        delta = 0.0

    if freqs.size > 1:
        f_hat = freqs[k0] + delta * (freqs[1] - freqs[0])
    else:
        f_hat = freqs[k0]

    tone = _complex_tone_at(times, volts_ac, f_hat, window)
    if abs(tone) < 1e-15:
        angle = np.angle(np.sum(spectrum[lo:hi]))
    else:
        angle = np.angle(tone)

    phasor = amplitude_peak * np.exp(1j * angle)
    return amplitude_peak, float(np.degrees(angle)), phasor, spectrum, lo, hi


def measure_single_channel(
    times: np.ndarray,
    volts: np.ndarray,
    target_hz: float,
    vin_peak: float,
    *,
    compute_phase: bool,
) -> tuple[float, float, float | None, complex | None]:
    amplitude_peak, phase_deg, phasor, _spectrum, _lo, _hi = _tone_metrics(times, volts, target_hz)
    gain_linear = max(amplitude_peak / max(vin_peak, 1e-15), 1e-15)
    gain_db = 20.0 * math.log10(gain_linear)

    if not compute_phase:
        return gain_linear, gain_db, None, None

    gain_complex = phasor / max(vin_peak, 1e-15)
    return gain_linear, gain_db, phase_deg, gain_complex


def measure_dual_channel(
    times_test: np.ndarray,
    volts_test: np.ndarray,
    times_ref: np.ndarray,
    volts_ref: np.ndarray,
    target_hz: float,
) -> tuple[float, float, float, complex]:
    amp_test, _phase_test, phasor_test, spectrum_t, lo_t, hi_t = _tone_metrics(times_test, volts_test, target_hz)
    amp_ref, _phase_ref, phasor_ref, spectrum_r, lo_r, hi_r = _tone_metrics(times_ref, volts_ref, target_hz)

    if abs(phasor_test) < 1e-15 or abs(phasor_ref) < 1e-15:
        phase_test = np.angle(np.sum(spectrum_t[lo_t:hi_t]))
        phase_ref = np.angle(np.sum(spectrum_r[lo_r:hi_r]))
        phasor_test = amp_test * np.exp(1j * phase_test)
        phasor_ref = amp_ref * np.exp(1j * phase_ref)

    gain_complex = phasor_test / (phasor_ref if abs(phasor_ref) > 1e-15 else 1e-15 + 0j)
    gain_linear = max(abs(gain_complex), 1e-15)
    gain_db = 20.0 * math.log10(gain_linear)
    phase_deg = float(np.degrees(np.angle(gain_complex)))
    return gain_linear, gain_db, phase_deg, gain_complex
