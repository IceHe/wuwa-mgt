import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.app.energy import (
    WAVEPLATE_RECOVER_SECONDS,
    add_resources,
    current_resources_from_full_time,
    full_time_from_current_waveplate_and_next_recover,
    seconds_to_next_waveplate_recover_from_full_time,
    spend_resources,
)


class EnergyPhaseTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 3, 31, 12, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    def test_spend_below_cap_preserves_next_recover_phase(self):
        full_at = self.now + timedelta(hours=5, minutes=56)
        current_wp, current_crystal = current_resources_from_full_time(full_at, 0, self.now)
        self.assertEqual((current_wp, current_crystal), (180, 0))

        next_wp, next_crystal = spend_resources(current_wp, current_crystal, 60)
        next_recover = seconds_to_next_waveplate_recover_from_full_time(full_at, self.now)
        shifted_full_at = full_time_from_current_waveplate_and_next_recover(next_wp, next_recover, self.now)

        self.assertEqual(next_crystal, 0)
        self.assertEqual(next_wp, 120)
        self.assertEqual(next_recover, 120)
        self.assertEqual(seconds_to_next_waveplate_recover_from_full_time(shifted_full_at, self.now), 120)

    def test_gain_below_cap_preserves_next_recover_phase(self):
        full_at = self.now + timedelta(hours=5, minutes=56)
        current_wp, current_crystal = current_resources_from_full_time(full_at, 0, self.now)
        self.assertEqual((current_wp, current_crystal), (180, 0))

        next_wp, next_crystal = add_resources(current_wp, current_crystal, 40)
        next_recover = seconds_to_next_waveplate_recover_from_full_time(full_at, self.now)
        shifted_full_at = full_time_from_current_waveplate_and_next_recover(next_wp, next_recover, self.now)

        self.assertEqual(next_crystal, 0)
        self.assertEqual(next_wp, 220)
        self.assertEqual(next_recover, 120)
        self.assertEqual(seconds_to_next_waveplate_recover_from_full_time(shifted_full_at, self.now), 120)

    def test_spend_from_full_starts_new_six_minute_cycle(self):
        full_at = self.now - timedelta(hours=3)
        current_wp, current_crystal = current_resources_from_full_time(full_at, 0, self.now)
        self.assertEqual((current_wp, current_crystal), (240, 15))

        next_wp, _ = spend_resources(current_wp, current_crystal, 60)
        shifted_full_at = full_time_from_current_waveplate_and_next_recover(
            next_wp,
            WAVEPLATE_RECOVER_SECONDS,
            self.now,
        )

        self.assertEqual(next_wp, 180)
        self.assertEqual(seconds_to_next_waveplate_recover_from_full_time(shifted_full_at, self.now), 360)


if __name__ == "__main__":
    unittest.main()
