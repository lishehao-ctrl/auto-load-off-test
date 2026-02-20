from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.enums import TriggerMode
from app.infrastructure.persistence.settings_repo_json import JsonSettingsRepository


class SettingsRepositoryTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "settings.json"
            repo = JsonSettingsRepository(config_path=config_path)

            settings = repo.load()
            settings.run_mode.trigger_mode = TriggerMode.TRIGGERED
            settings.setup.awg.visa_address = "USB::MOCK::INSTR"
            repo.save(settings)

            loaded = repo.load()
            self.assertEqual(loaded.run_mode.trigger_mode, TriggerMode.TRIGGERED)
            self.assertEqual(loaded.setup.awg.visa_address, "USB::MOCK::INSTR")


if __name__ == "__main__":
    unittest.main()
