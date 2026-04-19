"""
In-memory O(1) constraint tracking.

Verbatim move from scheduler_engine.py. No logic changes.
"""
from collections import defaultdict
from typing import Optional


class ConstraintTracker:
    """
    Tracks every assignment made during a scheduling run.
    assign() / unassign() implement atomic pair operations for labs.
    """

    def __init__(self):
        self._faculty_busy   = defaultdict(set)
        self._room_busy      = defaultdict(set)
        self._group_busy     = defaultdict(set)
        self._fac_day        = defaultdict(lambda: defaultdict(int))
        self._fac_week       = defaultdict(int)
        self._fac_slots      = defaultdict(lambda: defaultdict(list))
        self._group_day      = defaultdict(lambda: defaultdict(int))
        self._group_lab_days = defaultdict(set)
        self.section_room_count = defaultdict(lambda: defaultdict(int))

    def check(
        self,
        fac_id, room_id, group_id,
        day, slot,
        max_daily, max_weekly, max_consec,
    ) -> tuple[bool, str]:
        key = (day, slot)

        if fac_id is not None and fac_id in self._faculty_busy[key]:
            return False, f"faculty {fac_id} busy at {day} S{slot}"
        if room_id is not None and room_id in self._room_busy[key]:
            return False, f"room {room_id} busy at {day} S{slot}"
        if group_id is not None and group_id in self._group_busy[key]:
            return False, f"group {group_id} busy at {day} S{slot}"

        if fac_id is not None:
            if self._fac_week[fac_id] >= max_weekly:
                return False, f"faculty {fac_id} at weekly limit {max_weekly}"
            if self._fac_day[fac_id][day] >= max_daily:
                return False, f"faculty {fac_id} at daily limit {max_daily} on {day}"

            existing = sorted(self._fac_slots[fac_id][day])
            if existing:
                tentative = sorted(existing + [slot])
                run = 1
                for i in range(1, len(tentative)):
                    run = run + 1 if tentative[i] == tentative[i - 1] + 1 else 1
                    if run > max_consec:
                        return False, (
                            f"faculty {fac_id} would have {run} consecutive "
                            f"slots on {day} (max {max_consec})"
                        )
        return True, ""

    def check_pair(
        self,
        fac_id, room_id, group_id,
        day, s1, s2,
        max_daily, max_weekly, max_consec,
    ) -> tuple[bool, str]:
        ok, reason = self.check(fac_id, room_id, group_id, day, s1,
                                max_daily, max_weekly, max_consec)
        if not ok:
            return False, reason
        self.assign(fac_id, room_id, group_id, day, s1)
        ok2, reason2 = self.check(fac_id, room_id, group_id, day, s2,
                                   max_daily, max_weekly, max_consec)
        self.unassign(fac_id, room_id, group_id, day, s1)
        return ok2, reason2

    def assign(self, fac_id, room_id, group_id, day, slot):
        key = (day, slot)
        if fac_id is not None:
            self._faculty_busy[key].add(fac_id)
            self._fac_day[fac_id][day]  += 1
            self._fac_week[fac_id]      += 1
            self._fac_slots[fac_id][day].append(slot)
        if room_id is not None:
            self._room_busy[key].add(room_id)
        if group_id is not None:
            self._group_busy[key].add(group_id)
            self._group_day[group_id][day] += 1
            if room_id is not None:
                self.section_room_count[group_id][room_id] += 1

    def unassign(self, fac_id, room_id, group_id, day, slot):
        key = (day, slot)
        if fac_id is not None:
            self._faculty_busy[key].discard(fac_id)
            self._fac_day[fac_id][day]  -= 1
            self._fac_week[fac_id]      -= 1
            slots = self._fac_slots[fac_id][day]
            if slot in slots:
                slots.remove(slot)
        if room_id is not None:
            self._room_busy[key].discard(room_id)
        if group_id is not None:
            self._group_busy[key].discard(group_id)
            self._group_day[group_id][day] = max(
                0, self._group_day[group_id][day] - 1
            )

    def faculty_week_load(self, fac_id) -> int:
        return self._fac_week[fac_id]

    def faculty_day_load(self, fac_id, day) -> int:
        return self._fac_day[fac_id][day]

    def group_day_load(self, group_id, day) -> int:
        return self._group_day[group_id][day]

    def group_has_lab_today(self, group_id, day) -> bool:
        return day in self._group_lab_days[group_id]

    def mark_group_lab_day(self, group_id, day):
        self._group_lab_days[group_id].add(day)

    def is_group_free(self, group_id, day, slot) -> bool:
        return group_id not in self._group_busy.get((day, slot), set())

    def preferred_room_for_section(self, group_id) -> Optional[int]:
        """Return the room_id most used by this group so far, or None."""
        usage = self.section_room_count.get(group_id)
        if not usage:
            return None
        return max(usage, key=usage.get)
