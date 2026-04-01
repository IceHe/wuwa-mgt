import unittest
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.app.energy import (
    current_resources_from_full_time,
    seconds_to_next_waveplate_recover_from_full_time,
)

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/wuwa-mgt-test.db")

from backend.app.main import apply_energy_set
from backend.app.models import Account
from backend.app.schemas import EnergySetIn


class EnergySetTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 3, 31, 12, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    def _make_account(self, full_at: datetime, full_crystal: int) -> Account:
        return Account(
            account_id=1,
            id="test_id",
            abbr="t",
            nickname="test",
            full_waveplate_at=full_at,
            full_waveplate_crystal=full_crystal,
            is_active=True,
        )

    def test_change_crystal_only_below_cap_preserves_full_time_and_next_recover(self):
        full_at = self.now + timedelta(hours=5, minutes=56)
        account = self._make_account(full_at, 8)
        current_wp, _ = current_resources_from_full_time(account.full_waveplate_at, account.full_waveplate_crystal, self.now)
        before_next = seconds_to_next_waveplate_recover_from_full_time(account.full_waveplate_at, self.now)

        payload = EnergySetIn(current_waveplate=current_wp, current_waveplate_crystal=33)
        apply_energy_set(account, payload, self.now)

        self.assertEqual(account.full_waveplate_at, full_at)
        self.assertEqual(seconds_to_next_waveplate_recover_from_full_time(account.full_waveplate_at, self.now), before_next)
        after_wp, after_crystal = current_resources_from_full_time(
            account.full_waveplate_at,
            account.full_waveplate_crystal,
            self.now,
        )
        self.assertEqual(after_wp, current_wp)
        self.assertEqual(after_crystal, 33)

    def test_change_crystal_only_when_full_preserves_full_time(self):
        full_at = self.now - timedelta(hours=2)
        account = self._make_account(full_at, 3)
        current_wp, current_crystal = current_resources_from_full_time(
            account.full_waveplate_at,
            account.full_waveplate_crystal,
            self.now,
        )
        self.assertEqual(current_wp, 240)

        payload = EnergySetIn(current_waveplate=current_wp, current_waveplate_crystal=current_crystal + 20)
        apply_energy_set(account, payload, self.now)

        self.assertEqual(account.full_waveplate_at, full_at)
        after_wp, after_crystal = current_resources_from_full_time(
            account.full_waveplate_at,
            account.full_waveplate_crystal,
            self.now,
        )
        self.assertEqual(after_wp, 240)
        self.assertEqual(after_crystal, current_crystal + 20)


if __name__ == "__main__":
    unittest.main()
