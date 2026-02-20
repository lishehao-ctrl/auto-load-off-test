from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.models import SweepSpec
from app.domain.sweep_engine import compute_sampling_window_s, generate_frequency_points


class SweepEngineTests(unittest.TestCase):
    def test_linear_points_include_end(self) -> None:
        spec = SweepSpec(start_hz=1.0, stop_hz=5.0, step_hz=2.0, step_count=None, is_log=False)
        points = generate_frequency_points(spec)
        np.testing.assert_allclose(points, np.array([1.0, 3.0, 5.0]))

    def test_log_points_count(self) -> None:
        spec = SweepSpec(start_hz=1.0, stop_hz=100.0, step_hz=None, step_count=5, is_log=True)
        points = generate_frequency_points(spec)
        self.assertEqual(len(points), 5)
        self.assertAlmostEqual(points[0], 1.0)
        self.assertAlmostEqual(points[-1], 100.0)

    def test_sampling_window(self) -> None:
        window = compute_sampling_window_s(freq_hz=1e3, sample_rate_hz=1e6, points=10000)
        self.assertGreater(window, 0)


if __name__ == "__main__":
    unittest.main()
