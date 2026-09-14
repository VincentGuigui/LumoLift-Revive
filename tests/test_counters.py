import tempfile
import unittest
from pathlib import Path

from lumolift.counters import CounterStore


class CounterStoreTests(unittest.TestCase):
    def test_continues_after_a_same_day_raw_counter_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CounterStore(Path(directory) / "counters.json")
            self.assertEqual(store.update_steps(35, "2026-09-14").steps_displayed, 35)
            self.assertEqual(store.update_steps(0, "2026-09-14").steps_displayed, 35)
            self.assertEqual(store.update_steps(4, "2026-09-14").steps_displayed, 39)

    def test_restores_state_after_reopening(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "counters.json"
            CounterStore(path).update_stepsh(17, "2026-09-14")
            reopened = CounterStore(path)
            self.assertEqual(reopened.snapshot().stepsh_displayed, 17)

    def test_resets_daily_state_on_a_new_local_day(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CounterStore(Path(directory) / "counters.json")
            store.update_steps(50, "2026-09-14")
            self.assertEqual(store.update_steps(3, "2026-09-15").steps_displayed, 3)
