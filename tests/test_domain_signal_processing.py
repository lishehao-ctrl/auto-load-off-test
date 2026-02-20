from __future__ import annotations

import math
import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.signal_processing import measure_dual_channel, measure_single_channel


class SignalProcessingTests(unittest.TestCase):
    def test_single_channel_gain(self) -> None:
        fs = 200_000
        f0 = 2_000
        t = np.arange(0.0, 0.05, 1.0 / fs)

        vpeak = 0.5
        volts = vpeak * np.sin(2.0 * np.pi * f0 * t)

        gain, gain_db, phase, gain_complex = measure_single_channel(
            t,
            volts,
            f0,
            vin_peak=0.5,
            compute_phase=True,
        )

        self.assertAlmostEqual(gain, 1.0, delta=0.05)
        self.assertAlmostEqual(gain_db, 0.0, delta=0.5)
        self.assertIsNotNone(phase)
        self.assertIsNotNone(gain_complex)

    def test_dual_channel_gain_phase(self) -> None:
        fs = 200_000
        f0 = 5_000
        t = np.arange(0.0, 0.03, 1.0 / fs)

        ref = np.sin(2.0 * np.pi * f0 * t)
        phase_shift = math.radians(30.0)
        test = 2.0 * np.sin(2.0 * np.pi * f0 * t + phase_shift)

        gain, gain_db, phase_deg, _gain_complex = measure_dual_channel(t, test, t, ref, f0)

        self.assertAlmostEqual(gain, 2.0, delta=0.1)
        self.assertAlmostEqual(gain_db, 6.02, delta=0.8)
        self.assertAlmostEqual(phase_deg, 30.0, delta=5.0)


if __name__ == "__main__":
    unittest.main()
