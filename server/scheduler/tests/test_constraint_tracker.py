"""Unit tests for the ConstraintTracker (pure-Python, no DB)."""
from django.test import SimpleTestCase

from scheduler.engine.constraint_tracker import ConstraintTracker


class ConstraintTrackerBasics(SimpleTestCase):

    def setUp(self):
        self.t = ConstraintTracker()

    def test_check_passes_on_empty_state(self):
        ok, reason = self.t.check(
            fac_id=1, room_id=10, group_id=100,
            day="MON", slot=2,
            max_daily=4, max_weekly=18, max_consec=2,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_faculty_busy_same_slot_rejected(self):
        self.t.assign(1, 10, 100, "MON", 2)
        ok, reason = self.t.check(1, 11, 101, "MON", 2, 4, 18, 2)
        self.assertFalse(ok)
        self.assertIn("faculty", reason)

    def test_room_busy_same_slot_rejected(self):
        self.t.assign(1, 10, 100, "MON", 2)
        ok, reason = self.t.check(2, 10, 101, "MON", 2, 4, 18, 2)
        self.assertFalse(ok)
        self.assertIn("room", reason)

    def test_group_busy_same_slot_rejected(self):
        self.t.assign(1, 10, 100, "MON", 2)
        ok, reason = self.t.check(2, 11, 100, "MON", 2, 4, 18, 2)
        self.assertFalse(ok)
        self.assertIn("group", reason)

    def test_weekly_cap(self):
        for s in (1, 2, 3):
            self.t.assign(1, 10 + s, 100 + s, "MON", s)
        ok, reason = self.t.check(1, 20, 200, "TUE", 1, 4, 3, 3)
        self.assertFalse(ok)
        self.assertIn("weekly", reason)

    def test_daily_cap(self):
        for s in (1, 2, 3):
            self.t.assign(1, 10 + s, 100 + s, "MON", s)
        ok, reason = self.t.check(1, 20, 200, "MON", 4, 3, 18, 3)
        self.assertFalse(ok)
        self.assertIn("daily", reason)

    def test_max_consecutive_respected(self):
        self.t.assign(1, 10, 100, "MON", 1)
        self.t.assign(1, 11, 101, "MON", 2)
        ok, reason = self.t.check(1, 12, 102, "MON", 3, 4, 18, 2)
        self.assertFalse(ok)
        self.assertIn("consecutive", reason)

    def test_assign_unassign_symmetry(self):
        self.t.assign(1, 10, 100, "MON", 2)
        self.t.unassign(1, 10, 100, "MON", 2)
        ok, _ = self.t.check(1, 10, 100, "MON", 2, 4, 18, 2)
        self.assertTrue(ok, "unassign should fully reverse assign")

    def test_check_pair_rolls_back(self):
        ok, _ = self.t.check_pair(1, 10, 100, "MON", 1, 2, 4, 18, 2)
        self.assertTrue(ok)
        # After check_pair, no state should remain (assign was transient)
        ok2, _ = self.t.check(1, 10, 100, "MON", 1, 4, 18, 2)
        self.assertTrue(ok2)

    def test_preferred_room_for_section(self):
        self.t.assign(1, 10, 100, "MON", 1)
        self.t.assign(2, 10, 100, "MON", 2)
        self.t.assign(3, 11, 100, "MON", 3)
        self.assertEqual(self.t.preferred_room_for_section(100), 10)
