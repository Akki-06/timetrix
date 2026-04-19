"""
Difficulty-first scheduling ordering (improvement #1).

Ranks offerings by how hard they are to schedule. The hardest are placed
first while the solver still has flexibility. Factors:
    - Consecutive-slot requirement (labs, project work)
    - Faculty scarcity (few eligible teachers)
    - Room scarcity (lab rooms, off-day exclusions)
    - Combined/PE elective coordination overhead
    - Course priority (higher priority = schedule earlier)
"""
import logging

log = logging.getLogger(__name__)


class DifficultyScorer:
    """Computes a numeric difficulty for each offering. Higher = harder."""

    def __init__(
        self,
        offerings,
        eligible_faculty_map: dict,
        lab_room_count: int,
        theory_room_count: int,
    ):
        self.offerings            = offerings
        self.eligible_faculty_map = eligible_faculty_map  # offering_id -> list[faculty]
        self.lab_room_count       = max(lab_room_count, 1)
        self.theory_room_count    = max(theory_room_count, 1)

    def score(self, offering) -> float:
        course = offering.course
        d = 0.0

        # 1. Priority (5 = highest priority = schedule earliest)
        d += float(getattr(course, "priority", 3)) * 10.0

        # 2. Consecutive-slot courses are much harder (labs, project)
        if getattr(course, "requires_consecutive_slots", False):
            d += 40.0
        if getattr(course, "requires_lab_room", False):
            d += 25.0
            room_rarity = 1.0 / self.lab_room_count
            d += room_rarity * 30.0

        # 3. Faculty scarcity (fewer candidates = harder)
        eligible = self.eligible_faculty_map.get(offering.id, [])
        n_fac = max(len(eligible), 1)
        d += 30.0 / n_fac

        # 4. Weekly load — more sessions = harder
        needed = getattr(course, "min_weekly_lectures", 1)
        d += float(needed) * 4.0

        # 5. Combined / elective coordination
        if getattr(offering, "is_combined", False):
            d += 15.0
        if getattr(course, "course_type", "") == "PE":
            d += 12.0
        if getattr(offering, "elective_slot_group", None):
            d += 8.0

        # 6. Off-day restrictions on the group
        group = offering.student_group
        working_days = getattr(group, "working_days", None) or []
        if working_days and len(working_days) < 5:
            d += (5 - len(working_days)) * 6.0

        return d

    def sorted_offerings(self, reverse: bool = True) -> list:
        """Return offerings hardest-first when reverse=True."""
        scored = [(self.score(o), o) for o in self.offerings]
        scored.sort(key=lambda x: x[0], reverse=reverse)
        return [o for _, o in scored]
