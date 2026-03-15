"""
TIMETRIX — Scheduler Engine
=============================

HOW IT WORKS (read this before touching anything):

Admin flow:
  1. Admin enters faculty / rooms / courses / sections via Excel upload or form
  2. Django saves everything to DB
  3. Admin clicks "Generate Timetable" for e.g. BCA Sem V
  4. This engine runs, writes LectureAllocation rows, returns result to API

Scheduling order (critical — do not change without understanding why):
  Phase 1 — Load all data from DB into memory (one DB hit, not N)
  Phase 2 — Schedule LABS first
             Labs need 2 consecutive slots + a lab room — scarcest resource
             G1/G2 splits: both halves assigned simultaneously, same timeslot
             pair, different lab rooms
             Only ONE lab session per subject per week (sir's requirement)
  Phase 3 — Schedule THEORY
             Sort by Course.priority descending (important courses go first)
             For each offering → get eligible faculty → rank (day, slot, room)
             candidates by ML score → try best candidates first
             If hard constraint violated → backtrack, try next candidate
  Phase 4 — Save to DB atomically

Hard constraints (never violated):
  - Faculty not double-booked in same timeslot
  - Room not double-booked in same timeslot
  - Student group not double-booked in same timeslot
  - Faculty within max_weekly_load
  - Faculty within max_lectures_per_day
  - Faculty within max_consecutive_lectures
  - Labs always in 2 consecutive slots, lab rooms only
  - Lunch slot never assigned

Soft constraints (optimised by ML score):
  - Faculty preference for certain times
  - Historical room-course affinity
  - Even distribution across the week
  - Morning slots preferred for labs

ML integration:
  - RF scores each (faculty, room, day, slot) candidate 0.0–1.0
  - Candidates sorted by score before trying — best first
  - If ML models missing → heuristic fallback (scheduler still works)
  - Graceful degradation: partial schedules returned, not crashes
"""

import logging
import pickle
from collections import defaultdict
from pathlib import Path
from typing import Optional

from django.db import transaction

from academics.models    import AcademicTerm, CourseOffering, Course
from faculty.models      import Faculty, FacultySubjectEligibility, TeacherAvailability
from infrastructure.models import Room
from scheduler.models    import Timetable, TimeSlot, LectureAllocation

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR      = Path(__file__).resolve().parent.parent
TRAINED_DIR   = BASE_DIR / "ml_pipeline" / "trained"
RF_MODEL_PATH = TRAINED_DIR / "rf_model.pkl"
RF_META_PATH  = TRAINED_DIR / "rf_feature_metadata.pkl"
EMBED_PATH    = TRAINED_DIR / "node_embeddings.pkl"

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Max hours per week by faculty role — these are hard caps
MAX_HOURS_BY_ROLE = {
    "DEAN"    : 6,
    "HOD"     : 12,
    "SENIOR"  : 16,
    "REGULAR" : 18,
    "VISITING": 8,
}

DAYS = ["MON", "TUE", "WED", "THU", "FRI"]

# Day abbreviation → full name for ML scorer
DAY_FULL = {
    "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
    "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday"
}

# Canonical slot numbers (1-6, no lunch)
TEACHING_SLOTS = [1, 2, 3, 4, 5, 6]

# Slot pairs that are truly consecutive and don't span lunch
# Lunch comes after slot 4, so 4→5 is NOT consecutive (55-min gap)
# Valid consecutive pairs: (1,2), (2,3), (3,4), (5,6)
VALID_CONSECUTIVE_PAIRS = [(1, 2), (2, 3), (3, 4), (5, 6)]


# ─────────────────────────────────────────────────────────────────────────────
# ML SCORER
# Loads models once. Falls back to heuristics if files not found.
# ─────────────────────────────────────────────────────────────────────────────

class MLScorer:
    """
    Wraps RF model for candidate scoring.
    If models are missing, _heuristic_score() is used automatically.
    The scheduler does not know or care which path is taken.
    """

    def __init__(self):
        self.rf            = None
        self.scaler        = None
        self.embeddings    = {}
        self.max_hours_map = {}
        self._try_load()

    def _try_load(self):
        try:
            with open(RF_MODEL_PATH, "rb") as f:
                self.rf = pickle.load(f)
            with open(RF_META_PATH, "rb") as f:
                meta = pickle.load(f)
                self.scaler        = meta["scaler"]
                self.max_hours_map = meta.get("max_hours_map", {})
            with open(EMBED_PATH, "rb") as f:
                self.embeddings = pickle.load(f)
            log.info("ML scorer: loaded RF + embeddings.")
        except FileNotFoundError:
            log.warning(
                "ML models not found in ml_pipeline/trained/. "
                "Using heuristic scoring. Run gnn_model.py and "
                "random_forest_model.py to enable ML scoring."
            )

    @property
    def available(self):
        return self.rf is not None and self.scaler is not None

    def score(self, faculty_name: str, room_number: str,
              day: str, slot: int, is_lab: bool,
              contact_hours: int, semester: int,
              current_load: int) -> float:
        """
        Score a candidate (faculty, room, day, slot).
        Returns float in [0.0, 1.0]. Higher = better assignment.
        """
        if self.available:
            return self._ml_score(
                faculty_name, room_number, day, slot,
                is_lab, contact_hours, semester, current_load
            )
        return self._heuristic_score(day, slot, is_lab, current_load,
                                      self.max_hours_map.get(faculty_name, 18))

    def _ml_score(self, faculty_name, room_number, day, slot,
                  is_lab, contact_hours, semester, current_load) -> float:
        import numpy as np
        EMBED_DIM = 32
        ZERO      = np.zeros(EMBED_DIM, dtype=np.float32)

        fac_emb = self.embeddings.get(f"FAC::{faculty_name}", ZERO)
        rm_emb  = self.embeddings.get(f"RRM::{room_number}",  ZERO)
        ts_emb  = self.embeddings.get(
            f"TSL::{DAY_FULL.get(day, day)[:3].upper()}_S{slot}", ZERO
        )
        max_h = self.max_hours_map.get(faculty_name, 18)
        load_remaining = max(0, (max_h - current_load)) / 18.0

        import numpy as np
        manual = np.array([
            float(is_lab),
            0.0,
            contact_hours / 8.0,
            semester / 8.0,
            load_remaining,
            1.0 if slot <= 3 else 0.0,
        ], dtype=np.float32)

        feat        = np.concatenate([fac_emb, ts_emb, rm_emb, manual]).reshape(1, -1)
        feat_scaled = self.scaler.transform(feat)
        return float(self.rf.predict_proba(feat_scaled)[0][1])

    def _heuristic_score(self, day, slot, is_lab,
                          current_load, max_load) -> float:
        score = 0.5
        if is_lab and slot in (1, 2, 3):   score += 0.15  # morning labs preferred
        if slot in (2, 3, 4):              score += 0.05  # mid-morning slots
        if day in ("TUE", "WED", "THU"):   score += 0.03  # mid-week preferred
        if current_load >= max_load:        score -= 0.50  # overload penalty
        elif current_load >= max_load * 0.8: score -= 0.10
        return max(0.0, min(1.0, score))


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRAINT TRACKER
# In-memory O(1) conflict detection. Avoids N DB queries in hot scheduling loop.
# ─────────────────────────────────────────────────────────────────────────────

class ConstraintTracker:
    """
    Tracks all assigned slots in memory during one scheduling run.
    assign() / unassign() implement the backtracking stack.
    """

    def __init__(self):
        # (day, slot) → {faculty_id, ...}
        self._faculty_busy  : dict = defaultdict(set)
        # (day, slot) → {room_id, ...}
        self._room_busy     : dict = defaultdict(set)
        # (day, slot) → {group_id, ...}
        self._group_busy    : dict = defaultdict(set)
        # faculty_id → {day → count_of_sessions}
        self._fac_day       : dict = defaultdict(lambda: defaultdict(int))
        # faculty_id → total sessions this week
        self._fac_week      : dict = defaultdict(int)
        # faculty_id → {day → sorted list of assigned slots}
        self._fac_slots     : dict = defaultdict(lambda: defaultdict(list))

    def check(self, fac_id, room_id, group_id,
              day, slot, max_daily, max_weekly, max_consec) -> tuple[bool, str]:
        """
        Returns (True, "") if assignment is valid.
        Returns (False, reason) if it violates any hard constraint.
        """
        key = (day, slot)

        if fac_id   in self._faculty_busy[key]:
            return False, f"faculty {fac_id} busy at {day} S{slot}"
        if room_id  in self._room_busy[key]:
            return False, f"room {room_id} busy at {day} S{slot}"
        if group_id in self._group_busy[key]:
            return False, f"group {group_id} busy at {day} S{slot}"
        if self._fac_week[fac_id] >= max_weekly:
            return False, f"faculty {fac_id} at weekly limit {max_weekly}"
        if self._fac_day[fac_id][day] >= max_daily:
            return False, f"faculty {fac_id} at daily limit {max_daily} on {day}"

        # Consecutive lectures check
        existing = sorted(self._fac_slots[fac_id][day])
        if existing:
            tentative = sorted(existing + [slot])
            run = 1
            for i in range(1, len(tentative)):
                run = run + 1 if tentative[i] == tentative[i-1] + 1 else 1
                if run > max_consec:
                    return False, (
                        f"faculty {fac_id} would have {run} consecutive "
                        f"slots on {day} (max {max_consec})"
                    )
        return True, ""

    def check_pair(self, fac_id, room_id, group_id,
                   day, s1, s2,
                   max_daily, max_weekly, max_consec) -> tuple[bool, str]:
        """
        Check both slots of a consecutive lab pair atomically.
        Temporarily assigns s1 to correctly check s2.
        """
        ok, reason = self.check(fac_id, room_id, group_id, day, s1,
                                 max_daily, max_weekly, max_consec)
        if not ok:
            return False, reason
        # Temporarily assign s1 so s2 check sees it
        self.assign(fac_id, room_id, group_id, day, s1)
        ok2, reason2 = self.check(fac_id, room_id, group_id, day, s2,
                                   max_daily, max_weekly, max_consec)
        self.unassign(fac_id, room_id, group_id, day, s1)
        return ok2, reason2

    def assign(self, fac_id, room_id, group_id, day, slot):
        key = (day, slot)
        self._faculty_busy[key].add(fac_id)
        self._room_busy[key].add(room_id)
        self._group_busy[key].add(group_id)
        self._fac_day[fac_id][day]  += 1
        self._fac_week[fac_id]      += 1
        self._fac_slots[fac_id][day].append(slot)

    def unassign(self, fac_id, room_id, group_id, day, slot):
        """Backtrack — remove a previously made assignment."""
        key = (day, slot)
        self._faculty_busy[key].discard(fac_id)
        self._room_busy[key].discard(room_id)
        self._group_busy[key].discard(group_id)
        self._fac_day[fac_id][day]  -= 1
        self._fac_week[fac_id]      -= 1
        slots = self._fac_slots[fac_id][day]
        if slot in slots:
            slots.remove(slot)

    def faculty_week_load(self, fac_id) -> int:
        return self._fac_week[fac_id]


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class SchedulerEngine:
    """
    One instance per scheduling run.

    Usage (from Django view):
        engine = SchedulerEngine(timetable_id=timetable.id)
        result = engine.run()
        # result = {
        #   "status": "success" | "partial" | "failed",
        #   "allocations": 42,
        #   "avg_score": 0.81,
        #   "unscheduled": [],
        #   "ml_used": True,
        # }
    """

    def __init__(self, timetable_id: int):
        self.timetable_id = timetable_id
        self.timetable    = (
            Timetable.objects
            .select_related("term", "term__program")
            .get(pk=timetable_id)
        )
        self.term    = self.timetable.term
        self.ml      = MLScorer()
        self.tracker = ConstraintTracker()

        # Populated in _load()
        self.slot_map     = {}   # (day, slot_number) → TimeSlot obj
        self.lab_rooms    = []   # Room objs with room_type=LAB
        self.theory_rooms = []   # Room objs with room_type=THEORY
        self.faculty_meta = {}   # faculty_id → dict of constraints + availability
        self.offerings    = []   # CourseOffering objs for this term

        # Output buffers
        self.pending_saves: list[dict] = []   # allocations to write to DB
        self.unscheduled  : list[str]  = []   # human-readable unresolved items

    # ── PHASE 1: DATA LOADING ─────────────────────────────────────────────────

    def _load(self):
        """
        Pull everything needed from DB into memory.
        One place, one time — never query inside the scheduling loop.
        """
        log.info(f"Loading data for term: {self.term}")

        # Timeslots (exclude lunch)
        for ts in TimeSlot.objects.filter(is_lunch=False).order_by("slot_number"):
            self.slot_map[(ts.day, ts.slot_number)] = ts
        log.info(f"  Slots loaded: {len(self.slot_map)}")

        # Rooms from infrastructure app
        rooms = list(
            Room.objects.filter(is_active=True)
            .select_related("building")
            .order_by("-priority_weight", "room_number")
        )
        self.lab_rooms    = [r for r in rooms if r.room_type == "LAB"]
        self.theory_rooms = [r for r in rooms if r.room_type == "THEORY"]
        log.info(
            f"  Rooms: {len(self.lab_rooms)} labs, "
            f"{len(self.theory_rooms)} theory"
        )

        # Faculty availability + constraints
        for fac in Faculty.objects.filter(is_active=True).prefetch_related(
            "availabilities"
        ):
            avail_days        = set()
            avail_slots_by_day = defaultdict(set)

            for av in fac.availabilities.all():
                avail_days.add(av.day)
                for s in range(av.start_slot, av.end_slot + 1):
                    avail_slots_by_day[av.day].add(s)

            # No availability rows → available all days, all slots
            if not avail_days:
                avail_days = set(DAYS)
                for d in DAYS:
                    avail_slots_by_day[d] = set(TEACHING_SLOTS)

            # Hard cap is min of model field and role cap
            role_cap  = MAX_HOURS_BY_ROLE.get(fac.role, 18)
            max_weekly = min(fac.max_weekly_load, role_cap)

            self.faculty_meta[fac.id] = {
                "obj"         : fac,
                "avail_days"  : avail_days,
                "avail_slots" : dict(avail_slots_by_day),  # day → set of slots
                "max_weekly"  : max_weekly,
                "max_daily"   : fac.max_lectures_per_day,
                "max_consec"  : fac.max_consecutive_lectures,
            }

        log.info(f"  Faculty loaded: {len(self.faculty_meta)}")

        # Course offerings for this term
        self.offerings = list(
            CourseOffering.objects
            .filter(student_group__term=self.term)
            .select_related(
                "course",
                "student_group",
                "assigned_faculty",
            )
        )
        log.info(f"  Offerings loaded: {len(self.offerings)}")

    # ── ELIGIBLE FACULTY HELPER ───────────────────────────────────────────────

    def _eligible_faculty(self, offering: CourseOffering) -> list[Faculty]:
        """
        Return faculty eligible for this course, priority-sorted.
        If assigned_faculty is set on the offering, they come first.
        Falls back to all active faculty if no eligibility records exist.
        """
        qs = (
            FacultySubjectEligibility.objects
            .filter(course=offering.course, faculty__is_active=True)
            .select_related("faculty")
            .order_by("-priority_weight")
        )
        result = [e.faculty for e in qs]

        # Bubble assigned_faculty to the front
        if offering.assigned_faculty and offering.assigned_faculty in result:
            result = [offering.assigned_faculty] + \
                     [f for f in result if f != offering.assigned_faculty]
        elif offering.assigned_faculty:
            result = [offering.assigned_faculty] + result

        # Absolute fallback — should not happen in a well-configured system
        if not result:
            log.warning(
                f"No eligible faculty found for {offering.course.code}. "
                f"Using all active faculty as fallback."
            )
            result = list(Faculty.objects.filter(is_active=True))

        return result

    # ── CANDIDATE SCORING HELPER ──────────────────────────────────────────────

    def _score_candidate(self, fac: Faculty, room: Room,
                          day: str, slot: int,
                          is_lab: bool, offering: CourseOffering) -> float:
        return self.ml.score(
            faculty_name  = fac.name,
            room_number   = str(room.room_number),
            day           = day,
            slot          = slot,
            is_lab        = is_lab,
            contact_hours = offering.weekly_load or offering.course.min_weekly_lectures,
            semester      = self.term.semester,
            current_load  = self.tracker.faculty_week_load(fac.id),
        )

    # ── PHASE 2: LAB SCHEDULING ───────────────────────────────────────────────

    def _schedule_labs(self, lab_offerings: list):
        """
        Schedule all lab offerings.

        Rules enforced here:
        - 2 consecutive slots only (from VALID_CONSECUTIVE_PAIRS)
        - Lab room only
        - Only 1 lab session per subject per week (sir's requirement)
        - G1/G2: both halves scheduled simultaneously in different rooms,
          same consecutive slot pair, same day
        """
        log.info(f"LAB PHASE: {len(lab_offerings)} lab offerings")

        for offering in lab_offerings:
            course   = offering.course
            group    = offering.student_group
            group_id = group.id

            # Detect G1/G2 split from StudentGroup description or name
            is_split  = (
                "G1" in group.name.upper() or
                "G2" in group.name.upper() or
                "SPLIT" in (group.description or "").upper() or
                "G1/G2" in (group.description or "").upper()
            )

            eligible = self._eligible_faculty(offering)
            scheduled = False

            # ── Standard lab (no split) ───────────────────────────────────────
            if not is_split:
                for fac in eligible:
                    if scheduled:
                        break
                    meta = self.faculty_meta.get(fac.id)
                    if not meta:
                        continue

                    for room in self.lab_rooms:
                        if scheduled:
                            break
                        if room.capacity < group.strength:
                            continue

                        # Build scored candidates for all valid consecutive pairs
                        candidates = []
                        for day in meta["avail_days"]:
                            avail = meta["avail_slots"].get(day, set())
                            for s1, s2 in VALID_CONSECUTIVE_PAIRS:
                                if s1 not in avail or s2 not in avail:
                                    continue
                                if (day, s1) not in self.slot_map:
                                    continue
                                if (day, s2) not in self.slot_map:
                                    continue
                                score = self._score_candidate(
                                    fac, room, day, s1, True, offering
                                )
                                candidates.append((score, day, s1, s2))

                        # Try best-scored pair first
                        candidates.sort(reverse=True)
                        for score, day, s1, s2 in candidates:
                            ok, reason = self.tracker.check_pair(
                                fac.id, room.id, group_id, day, s1, s2,
                                meta["max_daily"], meta["max_weekly"],
                                meta["max_consec"]
                            )
                            if not ok:
                                continue

                            # Assign both slots
                            self.tracker.assign(fac.id, room.id, group_id, day, s1)
                            self.tracker.assign(fac.id, room.id, group_id, day, s2)

                            for slot in (s1, s2):
                                self.pending_saves.append({
                                    "offering_id": offering.id,
                                    "faculty_id" : fac.id,
                                    "room_id"    : room.id,
                                    "timeslot_id": self.slot_map[(day, slot)].id,
                                    "score"      : score,
                                })

                            log.info(
                                f"  LAB ✓ {course.code} | {fac.name} | "
                                f"Room {room.room_number} | "
                                f"{day} S{s1}+S{s2} | score={score:.3f}"
                            )
                            scheduled = True
                            break   # one lab per subject per week

            # ── G1/G2 split lab ───────────────────────────────────────────────
            else:
                # Find TWO free lab rooms on the same day+slot pair
                for fac in eligible:
                    if scheduled:
                        break
                    meta = self.faculty_meta.get(fac.id)
                    if not meta:
                        continue

                    for day in meta["avail_days"]:
                        if scheduled:
                            break
                        avail = meta["avail_slots"].get(day, set())

                        for s1, s2 in VALID_CONSECUTIVE_PAIRS:
                            if scheduled:
                                break
                            if s1 not in avail or s2 not in avail:
                                continue

                            # Need 2 free lab rooms at this pair
                            free_rooms = []
                            for room in self.lab_rooms:
                                if room.capacity < group.strength // 2:
                                    continue
                                ok, _ = self.tracker.check_pair(
                                    fac.id, room.id, group_id, day, s1, s2,
                                    meta["max_daily"], meta["max_weekly"],
                                    meta["max_consec"]
                                )
                                if ok:
                                    free_rooms.append(room)
                                if len(free_rooms) == 2:
                                    break

                            if len(free_rooms) < 2:
                                continue

                            # Assign: G1 → room A, G2 → room B
                            room_g1, room_g2 = free_rooms[0], free_rooms[1]
                            score = self._score_candidate(
                                fac, room_g1, day, s1, True, offering
                            )

                            for slot in (s1, s2):
                                # G1
                                self.tracker.assign(
                                    fac.id, room_g1.id, group_id, day, slot
                                )
                                self.pending_saves.append({
                                    "offering_id": offering.id,
                                    "faculty_id" : fac.id,
                                    "room_id"    : room_g1.id,
                                    "timeslot_id": self.slot_map[(day, slot)].id,
                                    "score"      : score,
                                })
                                # G2 (room only differs — same faculty, same slot)
                                self.tracker._room_busy[(day, slot)].add(room_g2.id)
                                self.pending_saves.append({
                                    "offering_id": offering.id,
                                    "faculty_id" : fac.id,
                                    "room_id"    : room_g2.id,
                                    "timeslot_id": self.slot_map[(day, slot)].id,
                                    "score"      : score,
                                })

                            log.info(
                                f"  LAB G1/G2 ✓ {course.code} | {fac.name} | "
                                f"R{room_g1.room_number}/R{room_g2.room_number} | "
                                f"{day} S{s1}+S{s2}"
                            )
                            scheduled = True

            if not scheduled:
                msg = f"LAB {course.code} ({group.name}) — no valid slot found"
                self.unscheduled.append(msg)
                log.warning(f"  UNSCHEDULED: {msg}")

    # ── PHASE 3: THEORY SCHEDULING WITH BACKTRACKING ──────────────────────────

    def _schedule_theory(self, theory_offerings: list):
        """
        Schedule theory sessions.

        Strategy:
        - Sort by Course.priority descending (most important courses first)
        - For each offering, build all (faculty, room, day, slot) candidates
          scored by ML
        - Try best-scored candidate first
        - If it violates any hard constraint → skip and try next (backtrack)
        - Distribute sessions across the week: same course not on same day twice
        """
        log.info(f"THEORY PHASE: {len(theory_offerings)} theory offerings")

        # High priority courses get slots first
        theory_offerings = sorted(
            theory_offerings,
            key=lambda o: -o.course.priority
        )

        for offering in theory_offerings:
            course   = offering.course
            group    = offering.student_group
            group_id = group.id
            needed   = course.min_weekly_lectures
            scheduled_count = 0

            # Track which days already have a session of this course
            # to ensure distribution across the week
            days_used: set[str] = set()

            eligible = self._eligible_faculty(offering)

            for fac in eligible:
                if scheduled_count >= needed:
                    break

                meta = self.faculty_meta.get(fac.id)
                if not meta:
                    continue

                # Build ALL valid candidates for this faculty
                candidates = []
                for day in meta["avail_days"]:
                    # Don't schedule same course twice on same day
                    if day in days_used:
                        continue
                    avail = meta["avail_slots"].get(day, set())
                    for slot in sorted(avail):
                        if slot not in TEACHING_SLOTS:
                            continue
                        if (day, slot) not in self.slot_map:
                            continue
                        score = self._score_candidate(
                            fac, self.theory_rooms[0] if self.theory_rooms
                            else Room(room_number="?"),
                            day, slot, False, offering
                        )
                        # Score each room too and keep best
                        best_room  = None
                        best_score = -1.0
                        for room in self.theory_rooms:
                            if room.capacity < group.strength:
                                continue
                            s = self._score_candidate(
                                fac, room, day, slot, False, offering
                            )
                            if s > best_score:
                                best_score = s
                                best_room  = room
                        if best_room is None:
                            continue
                        candidates.append((best_score, day, slot, fac, best_room))

                # Best score first
                candidates.sort(reverse=True)

                sessions_from_this_fac = 0
                # Each faculty takes at most ceil(needed/2) sessions
                # so multiple faculty can share the load
                max_per_fac = max(1, (needed + 1) // 2)

                for score, day, slot, fac_c, room in candidates:
                    if scheduled_count >= needed:
                        break
                    if sessions_from_this_fac >= max_per_fac:
                        break
                    if day in days_used:
                        continue

                    meta_c = self.faculty_meta.get(fac_c.id)
                    if not meta_c:
                        continue

                    ok, reason = self.tracker.check(
                        fac_c.id, room.id, group_id, day, slot,
                        meta_c["max_daily"],
                        meta_c["max_weekly"],
                        meta_c["max_consec"],
                    )
                    if not ok:
                        continue   # backtrack — try next candidate

                    # Assign
                    self.tracker.assign(fac_c.id, room.id, group_id, day, slot)
                    ts = self.slot_map[(day, slot)]
                    self.pending_saves.append({
                        "offering_id": offering.id,
                        "faculty_id" : fac_c.id,
                        "room_id"    : room.id,
                        "timeslot_id": ts.id,
                        "score"      : score,
                    })
                    days_used.add(day)
                    scheduled_count      += 1
                    sessions_from_this_fac += 1

                    log.info(
                        f"  THEORY ✓ {course.code} | {fac_c.name} | "
                        f"Room {room.room_number} | "
                        f"{day} S{slot} | score={score:.3f}"
                    )

            if scheduled_count < needed:
                msg = (
                    f"THEORY {course.code} ({group.name}) — "
                    f"only {scheduled_count}/{needed} sessions scheduled"
                )
                self.unscheduled.append(msg)
                log.warning(f"  UNSCHEDULED: {msg}")

    # ── PHASE 4: DB WRITE ─────────────────────────────────────────────────────

    @transaction.atomic
    def _save(self) -> int:
        """
        Write all allocations in one atomic transaction.
        If any DB-level unique constraint fires, the entire transaction
        rolls back — no partial corrupt state left in the DB.
        """
        log.info(f"Writing {len(self.pending_saves)} allocations to DB...")
        created = 0

        for alloc in self.pending_saves:
            LectureAllocation.objects.create(
                timetable_id           = self.timetable_id,
                course_offering_id     = alloc["offering_id"],
                faculty_id             = alloc["faculty_id"],
                room_id                = alloc["room_id"],
                timeslot_id            = alloc["timeslot_id"],
                hard_constraint_violated = False,
                soft_constraint_score  = round(alloc["score"], 4),
            )
            created += 1

        # Update timetable quality score
        if self.pending_saves:
            avg = sum(a["score"] for a in self.pending_saves) / len(self.pending_saves)
            self.timetable.total_constraint_score = round(avg, 4)
            self.timetable.save()

        log.info(f"  Saved {created} allocations.")
        return created

    # ── PUBLIC ENTRY POINT ────────────────────────────────────────────────────

    def run(self) -> dict:
        """
        Run the full scheduling pipeline.
        Returns a summary dict — passed directly back to the API response.
        """
        log.info(
            f"Scheduler started — timetable={self.timetable_id}, "
            f"term={self.term}, ml={'on' if self.ml.available else 'heuristic'}"
        )

        # Phase 1 — load
        self._load()

        if not self.offerings:
            return {
                "status"      : "failed",
                "reason"      : "No course offerings found for this term.",
                "allocations" : 0,
                "unscheduled" : [],
                "ml_used"     : self.ml.available,
            }

        # Split into lab and theory
        lab_offerings    = [
            o for o in self.offerings
            if o.course.requires_lab_room
            or o.course.requires_consecutive_slots
            or o.course.course_type == "LAB"
        ]
        theory_offerings = [
            o for o in self.offerings
            if o not in lab_offerings
        ]

        log.info(
            f"Offerings split: {len(lab_offerings)} labs, "
            f"{len(theory_offerings)} theory"
        )

        # Phase 2 — labs first
        if lab_offerings:
            self._schedule_labs(lab_offerings)

        # Phase 3 — theory
        if theory_offerings:
            self._schedule_theory(theory_offerings)

        # Phase 4 — save
        try:
            saved = self._save()
        except Exception as e:
            log.error(f"DB save failed: {e}")
            return {
                "status"      : "failed",
                "reason"      : str(e),
                "allocations" : 0,
                "unscheduled" : self.unscheduled,
                "ml_used"     : self.ml.available,
            }

        status = (
            "success" if not self.unscheduled
            else "partial"
        )

        result = {
            "status"      : status,
            "timetable_id": self.timetable_id,
            "allocations" : saved,
            "avg_score"   : self.timetable.total_constraint_score,
            "unscheduled" : self.unscheduled,
            "ml_used"     : self.ml.available,
        }

        log.info(
            f"Scheduler done — status={status}, "
            f"saved={saved}, unscheduled={len(self.unscheduled)}"
        )
        return result
