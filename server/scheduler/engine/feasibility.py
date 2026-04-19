"""
Forward-feasibility check (improvement #3).

Cheap arithmetic check run before committing an assignment: given remaining
unscheduled offerings and current occupancy, is it still *possible* to place
all of them? If the answer is no for the current move, skip it and try the
next candidate. Prevents greedy dead-ends.
"""
import logging
from collections import defaultdict

log = logging.getLogger(__name__)


class FeasibilityChecker:
    """
    Lightweight O(1)-ish forward check. Never guarantees success — it only
    rules out moves that make success impossible given remaining capacity.
    """

    def __init__(self, tracker, total_slots: int, theory_rooms: int, lab_rooms: int):
        self.tracker         = tracker
        self.total_slots     = total_slots
        self.theory_rooms    = max(theory_rooms, 1)
        self.lab_rooms       = max(lab_rooms, 1)

    def remaining_capacity(self, remaining_offerings) -> dict:
        """Return summary: sessions_needed, theory_slots_free, lab_slots_free."""
        sessions_needed = sum(
            o.course.min_weekly_lectures for o in remaining_offerings
        )
        theory_free = self.theory_rooms * self.total_slots - len(
            [k for k, s in self.tracker._room_busy.items() for _ in s]
        )
        return {
            "sessions_needed": sessions_needed,
            "theory_free": max(theory_free, 0),
        }

    def is_still_feasible(
        self,
        remaining_offerings,
        about_to_consume: int = 1,
    ) -> bool:
        """
        Return False if the upcoming assignment would make remaining sessions
        impossible to fit. We assume that every remaining session needs at
        least one (room, slot) pair.
        """
        if not remaining_offerings:
            return True
        # Approximate free room-slots across theory + lab pools.
        used_slots = sum(len(s) for s in self.tracker._room_busy.values())
        total_room_slots = (self.theory_rooms + self.lab_rooms) * self.total_slots
        free = total_room_slots - used_slots - about_to_consume

        needed = sum(o.course.min_weekly_lectures for o in remaining_offerings)
        if free < needed:
            log.debug(
                f"feasibility: free={free} < needed={needed} "
                f"(remaining_offerings={len(remaining_offerings)})"
            )
            return False
        return True

    def faculty_has_headroom(self, faculty, remaining_for_faculty: int) -> bool:
        """Does this faculty still have weekly capacity for `remaining_for_faculty`?"""
        from scheduler.engine.constants import TEACHING_SLOTS, DAYS
        week_load = self.tracker.faculty_week_load(faculty.id)
        # max_weekly defaults to 18 if not set
        cap = getattr(faculty, "max_weekly_hours", 18) or 18
        return (cap - week_load) >= remaining_for_faculty
