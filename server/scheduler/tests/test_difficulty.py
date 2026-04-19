"""Unit tests for DifficultyScorer."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from scheduler.engine.difficulty import DifficultyScorer


def _offering(oid, code, lab=False, consec=False, priority=3,
              lectures=3, ctype="PC", is_combined=False,
              elective_slot_group=None, working_days=None):
    course = SimpleNamespace(
        code=code,
        priority=priority,
        requires_lab_room=lab,
        requires_consecutive_slots=consec,
        min_weekly_lectures=lectures,
        course_type=ctype,
    )
    group = SimpleNamespace(
        name=f"SG_{oid}",
        working_days=working_days or ["MON", "TUE", "WED", "THU", "FRI"],
    )
    return SimpleNamespace(
        id=oid,
        course=course,
        student_group=group,
        is_combined=is_combined,
        elective_slot_group=elective_slot_group,
    )


class DifficultyOrdering(SimpleTestCase):

    def test_lab_ranks_above_theory(self):
        labs_offering   = _offering(1, "CS-L1", lab=True,  consec=True,  lectures=2)
        theory_offering = _offering(2, "CS-T1", lab=False, consec=False, lectures=3)

        ds = DifficultyScorer(
            offerings=[labs_offering, theory_offering],
            eligible_faculty_map={1: [object(), object()], 2: [object()] * 5},
            lab_room_count=2,
            theory_room_count=10,
        )
        ranked = ds.sorted_offerings(reverse=True)
        self.assertEqual(ranked[0].id, 1)

    def test_higher_priority_ranks_first(self):
        a = _offering(1, "A", priority=5)
        b = _offering(2, "B", priority=1)
        ds = DifficultyScorer(
            offerings=[b, a],
            eligible_faculty_map={1: [object()], 2: [object()]},
            lab_room_count=4,
            theory_room_count=10,
        )
        ranked = ds.sorted_offerings(reverse=True)
        self.assertEqual(ranked[0].id, 1)

    def test_faculty_scarcity_bumps_difficulty(self):
        scarce    = _offering(1, "RARE")
        plentiful = _offering(2, "COMMON")
        ds = DifficultyScorer(
            offerings=[plentiful, scarce],
            eligible_faculty_map={1: [object()], 2: [object()] * 20},
            lab_room_count=4,
            theory_room_count=10,
        )
        self.assertEqual(ds.sorted_offerings(reverse=True)[0].id, 1)
