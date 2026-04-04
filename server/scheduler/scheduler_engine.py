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
  Phase 1 — Load all data from DB into memoone DB hit, not N)
  Phase 2 — Schedule LABS firstry (
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
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from django.db import transaction

from academics.models    import AcademicTerm, CourseOffering, Course
from faculty.models      import Faculty, FacultySubjectEligibility, TeacherAvailability
from infrastructure.models import Room
from scheduler.models    import Timetable, TimeSlot, LectureAllocation, SchedulerConfig

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
    "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday",
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
        self.stats         = {}     # training-time pattern statistics
        self.threshold     = 0.5    # optimal classification threshold
        self._try_load()

    def _try_load(self):
        try:
            with open(RF_MODEL_PATH, "rb") as f:
                self.rf = pickle.load(f)

            if RF_META_PATH.exists():
                with open(RF_META_PATH, "rb") as f:
                    meta = pickle.load(f)
                    self.scaler            = meta.get("scaler")
                    self.max_hours_map     = meta.get("max_hours_map", {})
                    # stats dict carries slot/day popularity and faculty-course
                    # frequencies from training data — used for features 2-5,13-14
                    self.stats             = meta.get("stats", {})
                    # Optimal probability threshold from training (F1-maximising).
                    # Candidates below this score are tried last, not discarded.
                    self.threshold         = meta.get("optimal_threshold", 0.5)
            else:
                log.warning(
                    "RF metadata file not found. Using RF without scaler metadata."
                )

            with open(EMBED_PATH, "rb") as f:
                self.embeddings = pickle.load(f)
            log.info(f"ML scorer: loaded RF + embeddings "
                     f"(threshold={self.threshold:.3f}).")
        except FileNotFoundError:
            log.warning(
                "ML models not found in ml_pipeline/trained/. "
                "Using heuristic scoring. Run gnn_model.py and "
                "random_forest_model.py to enable ML scoring."
            )

    @property
    def available(self):
        return self.rf is not None

    def score(self, faculty_name: str, room_number: str,
              day: str, slot: int, is_lab: bool,
              contact_hours: int, semester: int,
              current_load: int,
              course_name: Optional[str] = None,
              room_type: Optional[str] = None,
              room_capacity: Optional[int] = None,
              requires_consecutive_slots: bool = False,
              is_elective: bool = False,
              section_name: Optional[str] = None,
              program_code: Optional[str] = None,
              current_load_today: int = 0,
              max_daily: int = 4) -> float:
        """
        Score a candidate (faculty, room, day, slot).
        Returns float in [0.0, 1.0]. Higher = better assignment.

        current_load_today : lectures already assigned to this faculty today
                             (dynamic state — improves features 13 & 15)
        max_daily          : faculty's per-day lecture cap
        """
        if self.available:
            return self._ml_score(
                faculty_name, room_number, day, slot,
                is_lab, contact_hours, semester, current_load,
                course_name=course_name,
                room_type=room_type,
                room_capacity=room_capacity,
                requires_consecutive_slots=requires_consecutive_slots,
                is_elective=is_elective,
                section_name=section_name,
                program_code=program_code,
                current_load_today=current_load_today,
                max_daily=max_daily,
            )
        return self._heuristic_score(day, slot, is_lab, current_load,
                                      self.max_hours_map.get(faculty_name, 18))

    def _ml_score(self, faculty_name, room_number, day, slot,
                  is_lab, contact_hours, semester, current_load,
                  course_name=None, room_type=None, room_capacity=None,
                  requires_consecutive_slots=False, is_elective=False,
                  section_name=None, program_code=None,
                  current_load_today: int = 0,
                  max_daily: int = 4) -> float:
        """
        Build a 112-dim feature vector and score via the trained RF model.
        Layout must match random_forest_model.py exactly:
          fac_emb[32] + ts_emb[32] + rm_emb[32] + manual[16] = 112
        Falls back to _heuristic_score() on any error.
        """
        try:
            import numpy as np
            EMBED_DIM = 32
            ZERO = np.zeros(EMBED_DIM, dtype=np.float32)

            # GNN embeddings keyed by node ID (same format as graph_builder.py)
            fac_emb = self.embeddings.get(f"FAC::{faculty_name}", ZERO)
            ts_emb  = self.embeddings.get(
                f"TSL::{DAY_FULL.get(day, day)[:3].upper()}_S{slot}", ZERO
            )
            rm_emb  = self.embeddings.get(f"RRM::{room_number}", ZERO)

            # --- 15 manual features (must match training order exactly) ---
            max_h = self.max_hours_map.get(faculty_name, 18)
            cur_load = current_load

            # 1: how much capacity the faculty has left this week
            load_remaining = max(0.0, (max_h - cur_load) / max(max_h, 1))

            # 2: did this faculty actually teach at this (day, slot) in training data?
            #    Training stats use full day names ("Monday"), engine uses abbreviations ("MON")
            day_full = DAY_FULL.get(day, day)
            actual_slots = self.stats.get("fac_actual_slots", {}).get(faculty_name, set())
            is_known_slot = 1.0 if (day_full, slot) in actual_slots else 0.0

            # 3: how often this faculty teaches this specific course (normalized)
            freq = self.stats.get("fac_course_freq", {}).get(
                (faculty_name, course_name or ""), 0
            )
            fac_max_freq = max(
                (v for (f, _), v in self.stats.get("fac_course_freq", {}).items()
                 if f == faculty_name),
                default=1,
            )
            fac_course_affinity = freq / max(fac_max_freq, 1)

            # 4: how popular this slot number is in the training data
            slot_pop = self.stats.get("slot_popularity", {}).get(slot, 0.5)

            # 5: how popular this day is in the training data
            #    day_popularity keys are full names ("Monday") from training CSV
            day_pop = self.stats.get("day_popularity", {}).get(day_full, 0.5)

            # 6-7: session type flags
            is_lab_f = float(is_lab)
            is_consecutive_lab = 1.0 if requires_consecutive_slots else 0.0

            # 8-9: time-of-day indicators
            is_morning = 1.0 if slot <= 3 else 0.0
            is_post_lunch = 1.0 if slot >= 5 else 0.0

            # 10: semester context (higher sem = more advanced course)
            sem_norm = float(semester) / 8.0

            # 11: how heavy the course is (weekly contact hours)
            contact_norm = float(contact_hours) / 8.0

            # 12: how many different courses this faculty teaches (versatility)
            breadth = self.stats.get("fac_course_count", {}).get(faculty_name, 1)
            breadth_norm = min(breadth / 10.0, 1.0)

            # 13: how full the faculty's day already is (live state from tracker)
            fac_today_ratio = float(current_load_today) / max(float(max_daily), 1.0)

            # 14: busyness of neighbouring slots (slot-1 and slot+1)
            adj_left = self.stats.get("slot_popularity", {}).get(slot - 1, 0.5)
            adj_right = self.stats.get("slot_popularity", {}).get(slot + 1, 0.5)
            slot_adjacent_density = (adj_left + adj_right) / 2.0

            # 15: early warning when faculty is close to their weekly cap
            near_weekly_cap = 1.0 if cur_load >= max_h * 0.85 else 0.0

            # 16: overload severity — how far above weekly cap
            overload_severity = max(0.0, (cur_load - max_h) / max(max_h, 1))

            manual = np.array([
                load_remaining,           # 1
                is_known_slot,            # 2
                fac_course_affinity,      # 3
                slot_pop,                 # 4
                day_pop,                  # 5
                is_lab_f,                 # 6
                is_consecutive_lab,       # 7
                is_morning,               # 8
                is_post_lunch,            # 9
                sem_norm,                 # 10
                contact_norm,             # 11
                breadth_norm,             # 12
                fac_today_ratio,          # 13
                slot_adjacent_density,    # 14
                near_weekly_cap,          # 15
                overload_severity,        # 16
            ], dtype=np.float32)

            feat = np.concatenate([fac_emb, ts_emb, rm_emb, manual]).reshape(1, -1)

            if self.scaler is not None:
                feat = self.scaler.transform(feat)

            return float(self.rf.predict_proba(feat)[0][1])

        except Exception as e:
            log.warning(f"ML scoring failed, falling back to heuristic: {e}")
            return self._heuristic_score(day, slot, is_lab, current_load,
                                         self.max_hours_map.get(faculty_name, 18))

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
        # group_id → {day → count_of_sessions}  (prevents all-day group overload)
        self._group_day     : dict = defaultdict(lambda: defaultdict(int))
        # group_id → set of days that already have a lab session
        self._group_lab_days: dict = defaultdict(set)

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
        self._group_day[group_id][day] += 1

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
        self._group_day[group_id][day] = max(0, self._group_day[group_id][day] - 1)

    def faculty_week_load(self, fac_id) -> int:
        return self._fac_week[fac_id]

    def faculty_day_load(self, fac_id, day) -> int:
        """Return how many sessions fac_id already has on this day."""
        return self._fac_day[fac_id][day]

    def group_day_load(self, group_id, day) -> int:
        """Return total sessions the student group already has on this day."""
        return self._group_day[group_id][day]

    def group_has_lab_today(self, group_id, day) -> bool:
        """Return True if this group already has a lab session on this day."""
        return day in self._group_lab_days[group_id]

    def mark_group_lab_day(self, group_id, day):
        """Record that this group now has a lab session on this day."""
        self._group_lab_days[group_id].add(day)


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
        # Load admin-configurable settings once per run
        self.config  = SchedulerConfig.get()

        # Populated in _load()
        self.slot_map     = {}   # (day, slot_number) → TimeSlot obj
        self.lab_rooms    = []   # Room objs with room_type=LAB
        self.theory_rooms = []   # Room objs with room_type=THEORY
        self.faculty_meta = {}   # faculty_id → dict of constraints + availability
        self.offerings    = []   # CourseOffering objs for this term

        # Output buffers
        self.pending_saves        : list[dict]          = []
        self.unscheduled          : list[str]           = []
        self.unscheduled_offerings: list[CourseOffering] = []  # for repair pass
        self.rejection_reasons    : dict[str, Counter]  = defaultdict(Counter)

    def _offering_label(self, offering: CourseOffering, prefix: str) -> str:
        return f"{prefix} {offering.course.code} ({offering.student_group.name})"

    def _top_reasons(self, label: str, limit: int = 3) -> list[dict]:
        return [
            {"reason": reason, "count": count}
            for reason, count in self.rejection_reasons.get(label, Counter()).most_common(limit)
        ]

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

        # Effective day list — include Saturday if admin enabled weekend classes
        active_days = DAYS + (["SAT"] if self.config.allow_weekend_classes else [])

        # Faculty availability + constraints
        for fac in Faculty.objects.filter(is_active=True).prefetch_related(
            "availabilities"
        ):
            avail_days        = set()
            avail_slots_by_day = defaultdict(set)

            if self.config.enforce_faculty_availability:
                for av in fac.availabilities.all():
                    avail_days.add(av.day)
                    for s in range(av.start_slot, av.end_slot + 1):
                        avail_slots_by_day[av.day].add(s)

            # No availability rows (or enforcement disabled) → open all active days
            if not avail_days:
                avail_days = set(active_days)
                for d in active_days:
                    avail_slots_by_day[d] = set(TEACHING_SLOTS)

            # Hard cap: min of individual faculty setting and role-based admin-configured cap
            role_cap   = self.config.role_cap(fac.role)
            max_weekly = min(fac.max_weekly_load, role_cap)

            # Also cap daily/consecutive limits by sensible floor — prevents
            # faculty with unusually high DB values from being over-scheduled.
            # Max daily is further capped at the number of teaching slots per day.
            max_daily  = min(fac.max_lectures_per_day,  len(TEACHING_SLOTS))
            max_consec = min(fac.max_consecutive_lectures, max_daily)

            # Filter avail_slots to only valid TEACHING_SLOTS (1-6).
            # TeacherAvailability.end_slot could be > 6 if seeded incorrectly.
            filtered_slots: dict = {}
            for d, slots in avail_slots_by_day.items():
                filtered = slots & set(TEACHING_SLOTS)
                if filtered:
                    filtered_slots[d] = filtered
            # Refill any days that became empty after filtering
            for d in avail_days:
                if d not in filtered_slots:
                    filtered_slots[d] = set(TEACHING_SLOTS)

            self.faculty_meta[fac.id] = {
                "obj"         : fac,
                "avail_days"  : avail_days,
                "avail_slots" : filtered_slots,  # day → set of valid slots (1-6 only)
                "max_weekly"  : max_weekly,
                "max_daily"   : max_daily,
                "max_consec"  : max_consec,
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

        # Reverse map used by the repair pass to recover (day, slot_number)
        # from a timeslot DB id without making extra queries.
        self.slot_id_to_key = {ts.id: key for key, ts in self.slot_map.items()}

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
                f"Using random sample of active faculty as fallback."
            )
            all_fac = list(Faculty.objects.filter(is_active=True))
            result = random.sample(all_fac, min(10, len(all_fac)))

        # If admin enabled senior-priority, bubble HOD/SENIOR to the top
        # (assigned_faculty already at front, so we only re-sort the rest)
        if self.config.prioritize_senior_faculty:
            _senior_roles = {"DEAN", "HOD", "SENIOR"}
            assigned = result[0] if result and offering.assigned_faculty == result[0] else None
            rest = result[1:] if assigned else result
            rest_sorted = sorted(
                rest,
                key=lambda f: (0 if f.role in _senior_roles else 1),
            )
            result = ([assigned] + rest_sorted) if assigned else rest_sorted

        return result

    # ── CANDIDATE SCORING HELPER ──────────────────────────────────────────────

    def _score_candidate(self, fac: Faculty, room: Room,
                          day: str, slot: int,
                          is_lab: bool, offering: CourseOffering) -> float:
        course    = offering.course
        group     = offering.student_group
        fac_meta  = self.faculty_meta.get(fac.id, {})
        # Live dynamic state — how many sessions this faculty already has today
        today_load = self.tracker.faculty_day_load(fac.id, day)
        max_daily  = fac_meta.get("max_daily", 4)
        return self.ml.score(
            faculty_name               = fac.name,
            room_number                = str(room.room_number),
            day                        = day,
            slot                       = slot,
            is_lab                     = is_lab,
            contact_hours              = offering.weekly_load or course.min_weekly_lectures,
            semester                   = self.term.semester,
            current_load               = self.tracker.faculty_week_load(fac.id),
            course_name                = course.name,
            room_type                  = room.room_type,
            room_capacity              = room.capacity,
            requires_consecutive_slots = bool(course.requires_consecutive_slots),
            is_elective                = course.course_type in {"OE", "PE"},
            section_name               = group.name,
            program_code               = getattr(self.term.program, "code", None),
            current_load_today         = today_load,
            max_daily                  = max_daily,
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
            offering_label = self._offering_label(offering, "LAB")

            # Detect G1/G2 split from StudentGroup description or name
            is_split  = (
                "G1" in group.name.upper() or
                "G2" in group.name.upper() or
                "SPLIT" in (group.description or "").upper() or
                "G1/G2" in (group.description or "").upper()
            )

            # Auto-detect split: if no single lab room can fit the full group,
            # fall back to G1/G2 split (half-group per room)
            if not is_split:
                room_pool_check = self.lab_rooms if course.requires_lab_room else self.theory_rooms
                if room_pool_check and all(
                    r.capacity < group.strength for r in room_pool_check
                ):
                    log.info(
                        f"  LAB {course.code} ({group.name}): no single room fits "
                        f"strength={group.strength} — auto-switching to G1/G2 split"
                    )
                    is_split = True

            eligible = self._eligible_faculty(offering)
            if not eligible:
                self.rejection_reasons[offering_label]["no_eligible_faculty"] += 1
            scheduled = False

            # ── Standard lab (no split) ───────────────────────────────────────
            if not is_split:
                for fac in eligible:
                    if scheduled:
                        break
                    meta = self.faculty_meta.get(fac.id)
                    if not meta:
                        continue

                    room_pool = self.lab_rooms if course.requires_lab_room else self.theory_rooms
                    for room in room_pool:
                        if scheduled:
                            break
                        if room.capacity < group.strength:
                            continue

                        # Build scored candidates for all valid consecutive pairs.
                        # LIMIT: max 1 lab per group per day to prevent all-day labs.
                        candidates = []
                        for day in meta["avail_days"]:
                            # Skip this day if this group already has a lab today
                            if self.tracker.group_has_lab_today(group_id, day):
                                continue
                            # Also skip if group is already overloaded this day
                            # (pre-existing labs from earlier iterations count)
                            if self.tracker.group_day_load(group_id, day) >= len(TEACHING_SLOTS) - 1:
                                continue
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
                            # Mark this group as having a lab today so no other
                            # lab offering can be placed on the same day
                            self.tracker.mark_group_lab_day(group_id, day)

                            for slot in (s1, s2):
                                self.pending_saves.append({
                                    "offering_id": offering.id,
                                    "student_group_id": group.id,
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
                        # LIMIT: no more than 1 lab per group per day (G1/G2 path)
                        if self.tracker.group_has_lab_today(group_id, day):
                            continue
                        if self.tracker.group_day_load(group_id, day) >= len(TEACHING_SLOTS) - 1:
                            continue
                        avail = meta["avail_slots"].get(day, set())

                        for s1, s2 in VALID_CONSECUTIVE_PAIRS:
                            if scheduled:
                                break
                            if s1 not in avail or s2 not in avail:
                                continue

                            # Need 2 free rooms at this pair
                            room_pool = self.lab_rooms if course.requires_lab_room else self.theory_rooms
                            free_rooms = []
                            for room in room_pool:
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
                                # G1 — primary record (faculty + group tracked here)
                                self.tracker.assign(
                                    fac.id, room_g1.id, group_id, day, slot
                                )
                                self.pending_saves.append({
                                    "offering_id": offering.id,
                                    "student_group_id": group.id,
                                    "faculty_id" : fac.id,
                                    "room_id"    : room_g1.id,
                                    "timeslot_id": self.slot_map[(day, slot)].id,
                                    "score"      : score,
                                })
                                # G2 — mark room busy in tracker only (no DB record
                                # to avoid violating unique_faculty_per_slot and
                                # unique_group_per_slot constraints)
                                self.tracker._room_busy[(day, slot)].add(room_g2.id)

                            # Mark this group as having a lab today (G1/G2 path too)
                            self.tracker.mark_group_lab_day(group_id, day)
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
            offering_label = self._offering_label(offering, "THEORY")
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

                # Build ALL valid candidates for this faculty.
                # Score (faculty, day, slot) ONCE with the first viable room —
                # this is the dominant ML signal. Room selection then picks the
                # best-capacity-fit available room without extra ML calls.
                viable_rooms = [
                    r for r in self.theory_rooms
                    if r.capacity >= group.strength
                ]
                if not viable_rooms:
                    self.rejection_reasons[offering_label]["room_capacity_too_small"] += 1

                # Max theory sessions this group can have in one day.
                # Labs take 2 slots; leave at least 2 free slots per day for theory variety.
                max_group_sessions_per_day = max(2, len(TEACHING_SLOTS) - 2)

                candidates = []
                sample_room = viable_rooms[0] if viable_rooms else None
                for day in meta["avail_days"]:
                    # Don't schedule same course twice on same day
                    if day in days_used:
                        self.rejection_reasons[offering_label]["same_course_day_distribution_block"] += 1
                        continue
                    if not sample_room:
                        self.rejection_reasons[offering_label]["no_room_fit_for_slot"] += 1
                        continue
                    # Skip days where this group is already heavily scheduled
                    if self.tracker.group_day_load(group_id, day) >= max_group_sessions_per_day:
                        self.rejection_reasons[offering_label]["group_daily_limit_reached"] += 1
                        continue
                    avail = meta["avail_slots"].get(day, set())
                    for slot in sorted(avail):
                        if slot not in TEACHING_SLOTS:
                            continue
                        if (day, slot) not in self.slot_map:
                            continue
                        # Single ML call per (fac, day, slot)
                        score = self._score_candidate(
                            fac, sample_room, day, slot, False, offering
                        )
                        candidates.append((score, day, slot, fac, viable_rooms))

                if not candidates:
                    self.rejection_reasons[offering_label]["no_candidates_generated_for_faculty"] += 1

                # Best score first
                candidates.sort(reverse=True)

                sessions_from_this_fac = 0
                # Each faculty takes at most ceil(needed/2) sessions
                # so multiple faculty can share the load
                max_per_fac = max(1, (needed + 1) // 2)

                for score, day, slot, fac_c, room_pool in candidates:
                    if scheduled_count >= needed:
                        break
                    if sessions_from_this_fac >= max_per_fac:
                        break
                    if day in days_used:
                        continue
                    # Re-check group daily limit at assignment time (count may have changed)
                    if self.tracker.group_day_load(group_id, day) >= max_group_sessions_per_day:
                        continue

                    meta_c = self.faculty_meta.get(fac_c.id)
                    if not meta_c:
                        continue

                    # Pick the first available room from the viable pool
                    room = next(
                        (r for r in room_pool
                         if r.id not in self.tracker._room_busy.get((day, slot), set())),
                        None,
                    )
                    if room is None:
                        self.rejection_reasons[offering_label]["no_room_available_for_slot"] += 1
                        continue

                    ok, reason = self.tracker.check(
                        fac_c.id, room.id, group_id, day, slot,
                        meta_c["max_daily"],
                        meta_c["max_weekly"],
                        meta_c["max_consec"],
                    )
                    if not ok:
                        self.rejection_reasons[offering_label][reason] += 1
                        continue   # backtrack — try next candidate

                    # Assign
                    self.tracker.assign(fac_c.id, room.id, group_id, day, slot)
                    ts = self.slot_map[(day, slot)]
                    self.pending_saves.append({
                        "offering_id": offering.id,
                        "student_group_id": group.id,
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
                if not self.rejection_reasons[offering_label]:
                    self.rejection_reasons[offering_label]["insufficient_feasible_candidates"] += 1
                msg = (
                    f"THEORY {course.code} ({group.name}) — "
                    f"only {scheduled_count}/{needed} sessions scheduled"
                )
                # Track the offering object for the repair pass
                self.unscheduled_offerings.append(offering)
                self.unscheduled.append(msg)
                log.warning(f"  UNSCHEDULED: {msg}")

    # ── PHASE 3b: REPAIR PASS ─────────────────────────────────────────────────

    def _repair_unscheduled(self) -> list:
        """
        Second-chance pass for theory offerings that were left unscheduled.

        The greedy pass in _schedule_theory enforces two soft rules that can
        cause unnecessary failures:
          a) same course not on same day twice (day-distribution)
          b) only try faculty in their declared avail_days

        The repair pass relaxes BOTH to try harder, while still enforcing
        every hard constraint (faculty/room/group busy, daily/weekly caps,
        consecutive limit).

        Returns the list of offerings that were successfully repaired so the
        caller can remove them from self.unscheduled.
        """
        if not self.unscheduled_offerings:
            return []

        log.info(
            f"REPAIR PASS: trying to fix "
            f"{len(self.unscheduled_offerings)} unscheduled offering(s)"
        )

        fixed = []

        for offering in self.unscheduled_offerings:
            course   = offering.course
            group    = offering.student_group
            group_id = group.id
            needed   = course.min_weekly_lectures

            # How many sessions of this course are already scheduled
            # (the greedy pass may have placed some but not all)
            already = sum(
                1 for a in self.pending_saves
                if a["offering_id"] == offering.id
            )
            still_need = needed - already
            if still_need <= 0:
                fixed.append(offering)
                continue

            eligible = self._eligible_faculty(offering)
            scheduled_now = 0

            for fac in eligible:
                if scheduled_now >= still_need:
                    break
                meta = self.faculty_meta.get(fac.id)
                if not meta:
                    continue

                # Relaxation: try ALL five days, not just avail_days.
                viable_rooms = [
                    r for r in self.theory_rooms
                    if r.capacity >= group.strength
                ]
                sample_room = viable_rooms[0] if viable_rooms else None
                candidates = []
                for day in DAYS:
                    if not sample_room:
                        break
                    avail = meta["avail_slots"].get(day, set(TEACHING_SLOTS))
                    for slot in sorted(avail):
                        if slot not in TEACHING_SLOTS:
                            continue
                        if (day, slot) not in self.slot_map:
                            continue
                        score = self._score_candidate(
                            fac, sample_room, day, slot, False, offering
                        )
                        candidates.append((score, day, slot, fac, viable_rooms))

                # Best score first — same as greedy pass
                candidates.sort(reverse=True)

                for score, day, slot, fac_c, room_pool in candidates:
                    if scheduled_now >= still_need:
                        break
                    # Respect group daily session cap even in the repair pass
                    max_group_daily = max(2, len(TEACHING_SLOTS) - 2)
                    if self.tracker.group_day_load(group_id, day) >= max_group_daily:
                        continue
                    meta_c = self.faculty_meta.get(fac_c.id)
                    if not meta_c:
                        continue

                    room = next(
                        (r for r in room_pool
                         if r.id not in self.tracker._room_busy.get((day, slot), set())),
                        None,
                    )
                    if room is None:
                        continue

                    ok, reason = self.tracker.check(
                        fac_c.id, room.id, group_id, day, slot,
                        meta_c["max_daily"],
                        meta_c["max_weekly"],
                        meta_c["max_consec"],
                    )
                    if not ok:
                        continue

                    # Assign
                    self.tracker.assign(fac_c.id, room.id, group_id, day, slot)
                    ts = self.slot_map[(day, slot)]
                    self.pending_saves.append({
                        "offering_id"     : offering.id,
                        "student_group_id": group.id,
                        "faculty_id"      : fac_c.id,
                        "room_id"         : room.id,
                        "timeslot_id"     : ts.id,
                        "score"           : score,
                    })
                    scheduled_now += 1
                    log.info(
                        f"  REPAIR ✓ {course.code} | {fac_c.name} | "
                        f"{day} S{slot} | score={score:.3f}"
                    )

            if scheduled_now >= still_need:
                fixed.append(offering)
                log.info(
                    f"  REPAIR: {course.code} ({group.name}) fully resolved."
                )
            elif scheduled_now > 0:
                # Partially resolved — reduce the unscheduled message
                fixed.append(offering)   # remove the old message; will re-add partial
                log.info(
                    f"  REPAIR: {course.code} ({group.name}) "
                    f"partially resolved (+{scheduled_now} sessions)."
                )

        log.info(
            f"REPAIR PASS done: {len(fixed)}/{len(self.unscheduled_offerings)} "
            "offerings improved."
        )
        return fixed

    # ── PHASE 4: DB WRITE ─────────────────────────────────────────────────────

    @transaction.atomic
    def _save(self) -> int:
        """
        Write all allocations in one atomic transaction using bulk_create.
        Deduplicates pending_saves first to guard against any scheduler
        path that accidentally generates duplicate (faculty+timeslot) or
        (room+timeslot) or (group+timeslot) entries, which would cause an
        IntegrityError and roll back the entire save.
        """
        log.info(f"Writing {len(self.pending_saves)} allocations to DB...")

        # --- Deduplicate to prevent DB unique-constraint violations ---
        seen_fac_slot   = set()
        seen_room_slot  = set()
        seen_grp_slot   = set()
        deduped = []
        skipped = 0
        for alloc in self.pending_saves:
            key_f = (alloc["faculty_id"],       alloc["timeslot_id"])
            key_r = (alloc["room_id"],           alloc["timeslot_id"])
            key_g = (alloc["student_group_id"],  alloc["timeslot_id"])
            if key_f in seen_fac_slot or key_r in seen_room_slot or key_g in seen_grp_slot:
                log.warning(
                    f"  Dedup-skip: fac={alloc['faculty_id']} "
                    f"room={alloc['room_id']} grp={alloc['student_group_id']} "
                    f"ts={alloc['timeslot_id']}"
                )
                skipped += 1
                continue
            seen_fac_slot.add(key_f)
            seen_room_slot.add(key_r)
            seen_grp_slot.add(key_g)
            deduped.append(alloc)

        if skipped:
            log.warning(f"  Dedup removed {skipped} duplicate allocation(s).")

        objs = [
            LectureAllocation(
                timetable_id             = self.timetable_id,
                course_offering_id       = alloc["offering_id"],
                student_group_id         = alloc["student_group_id"],
                faculty_id               = alloc["faculty_id"],
                room_id                  = alloc["room_id"],
                timeslot_id              = alloc["timeslot_id"],
                hard_constraint_violated = False,
                soft_constraint_score    = round(float(alloc["score"]), 4),
            )
            for alloc in deduped
        ]

        bulk_ok = False
        try:
            with transaction.atomic():
                LectureAllocation.objects.bulk_create(objs)
            bulk_ok = True
        except Exception as bulk_err:
            log.error(
                f"  bulk_create failed ({bulk_err}). "
                "Falling back to per-record saves..."
            )

        if not bulk_ok:
            # The nested savepoint was rolled back; outer transaction is clean.
            # Save records one by one so we can skip individual violators.
            saved_indices = []
            for i, (alloc, obj) in enumerate(zip(deduped, objs)):
                try:
                    with transaction.atomic():
                        obj.pk = None  # ensure INSERT not UPDATE
                        obj.save()
                    saved_indices.append(i)
                except Exception as row_err:
                    log.warning(
                        f"  Skipped: fac={obj.faculty_id} "
                        f"room={obj.room_id} ts={obj.timeslot_id}: {row_err}"
                    )
            deduped = [deduped[i] for i in saved_indices]

        created = len(deduped)

        # Update timetable quality score
        if deduped:
            avg = sum(a["score"] for a in deduped) / len(deduped)
            self.timetable.total_constraint_score = round(avg, 4)
            self.timetable.save(update_fields=["total_constraint_score"])

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

        # Phase 3b — repair pass
        # Attempt to recover offerings the greedy pass couldn't schedule by
        # relaxing the day-distribution soft constraint and trying all days.
        if self.unscheduled_offerings:
            fixed = self._repair_unscheduled()
            if fixed:
                fixed_ids = {id(o) for o in fixed}
                # Rebuild unscheduled list: remove entries for repaired offerings
                self.unscheduled = [
                    msg for msg in self.unscheduled
                    if not any(
                        msg.startswith(f"THEORY {o.course.code} ({o.student_group.name})")
                        for o in fixed
                    )
                ]
                self.unscheduled_offerings = [
                    o for o in self.unscheduled_offerings
                    if id(o) not in fixed_ids
                ]

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
            "unscheduled_reasons": {
                msg.split(" — ")[0]: self._top_reasons(msg.split(" — ")[0])
                for msg in self.unscheduled
            },
            "ml_used"     : self.ml.available,
        }

        log.info(
            f"Scheduler done — status={status}, "
            f"saved={saved}, unscheduled={len(self.unscheduled)}"
        )
        return result
