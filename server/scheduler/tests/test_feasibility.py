"""Unit tests for FeasibilityChecker."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from scheduler.engine.constraint_tracker import ConstraintTracker
from scheduler.engine.feasibility import FeasibilityChecker


def _offering(lectures=3):
    course = SimpleNamespace(min_weekly_lectures=lectures)
    return SimpleNamespace(course=course)


class FeasibilitySmoke(SimpleTestCase):

    def test_empty_remaining_always_feasible(self):
        fc = FeasibilityChecker(ConstraintTracker(), total_slots=30,
                                theory_rooms=5, lab_rooms=2)
        self.assertTrue(fc.is_still_feasible([], about_to_consume=1))

    def test_detects_capacity_overflow(self):
        # 30 total slots * 7 rooms = 210 room-slots. But for this test,
        # simulate 5 rooms total with only 1 slot each = 5 slots.
        fc = FeasibilityChecker(ConstraintTracker(), total_slots=1,
                                theory_rooms=3, lab_rooms=2)
        remaining = [_offering(lectures=6)]  # needs 6 slots, only 5 exist
        self.assertFalse(fc.is_still_feasible(remaining, about_to_consume=0))

    def test_allows_move_with_headroom(self):
        fc = FeasibilityChecker(ConstraintTracker(), total_slots=6,
                                theory_rooms=3, lab_rooms=2)
        remaining = [_offering(lectures=3)]
        self.assertTrue(fc.is_still_feasible(remaining, about_to_consume=1))
