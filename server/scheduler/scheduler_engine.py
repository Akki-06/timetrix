"""
TIMETRIX — Scheduler Engine v4

Four-phase greedy constraint-satisfaction engine with ML-assisted ranking.

Phase 1 : LOAD       — one DB hit per table, everything in memory
Phase 2 : LABS       — scarcest resource first, section-by-section
Phase 3 : THEORY     — 3a electives  3b combined  3c standard  3d repair
Phase 4 : SAVE       — atomic bulk_create with deduplication

Hard constraints enforced in ConstraintTracker (O(1) in-memory).
ML (GNN-embeddings + Random Forest) ranks candidates; room selected
deterministically via program-affinity priority tiers.
"""

import logging
import math
import pickle
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from django.db import transaction

from academics.models      import AcademicTerm, CourseOffering, Course, StudentGroup
from faculty.models        import Faculty, FacultySubjectEligibility, TeacherAvailability
from infrastructure.models import Room, ProgramRoomMapping
from scheduler.models      import Timetable, TimeSlot, LectureAllocation, SchedulerConfig

log = logging.getLogger(__name__)

# ── path constants ────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent
TRAINED_DIR   = BASE_DIR / "ml_pipeline" / "trained"
RF_MODEL_PATH = TRAINED_DIR / "rf_model.pkl"
RF_META_PATH  = TRAINED_DIR / "rf_feature_metadata.pkl"
EMBED_PATH    = TRAINED_DIR / "node_embeddings.pkl"

# ── scheduling constants ──────────────────────────────────────────────────────
DAYS               = ["MON", "TUE", "WED", "THU", "FRI"]
DAY_FULL           = {
    "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
    "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday",
}
TEACHING_SLOTS     = [1, 2, 3, 4, 5, 6]
# Slot 4→5 spans the lunch break — NOT consecutive
VALID_CONSECUTIVE_PAIRS = [(1, 2), (2, 3), (3, 4), (5, 6)]


# ═════════════════════════════════════════════════════════════════════════════
# ML SCORER
# ═════════════════════════════════════════════════════════════════════════════

class MLScorer:
    """
    Wraps the GNN-embedding + Random-Forest pipeline for candidate scoring.

    At scoring time the GNN embeddings are already pre-computed and stored in
    node_embeddings.pkl — no graph inference happens at runtime.

    Falls back to heuristic scoring if model files are missing.
    """

    def __init__(self):
        self.rf            = None
        self.scaler        = None
        self.embeddings: dict = {}
        self.max_hours_map: dict = {}
        self.stats: dict   = {}
        self.threshold     = 0.5
        self._fac_max_freq: dict = {}
        self._try_load()

    def _try_load(self):
        try:
            with open(RF_MODEL_PATH, "rb") as f:
                self.rf = pickle.load(f)
            if RF_META_PATH.exists():
                with open(RF_META_PATH, "rb") as f:
                    meta = pickle.load(f)
                self.scaler        = meta.get("scaler")
                self.max_hours_map = meta.get("max_hours_map", {})
                self.stats         = meta.get("stats", {})
                self.threshold     = meta.get("optimal_threshold", 0.5)
                # Pre-compute per-faculty max course frequency to avoid O(N) scan per score call
                self._fac_max_freq: dict = {}
                for (fac, _), v in self.stats.get("fac_course_freq", {}).items():
                    if v > self._fac_max_freq.get(fac, 0):
                        self._fac_max_freq[fac] = v
            else:
                log.warning("RF metadata not found; running without scaler/stats.")
                self._fac_max_freq = {}
            with open(EMBED_PATH, "rb") as f:
                self.embeddings = pickle.load(f)
            log.info(f"ML scorer: loaded RF + embeddings (threshold={self.threshold:.3f}).")
        except FileNotFoundError:
            log.warning(
                "ML models not found in ml_pipeline/trained/. "
                "Using heuristic scoring only. "
                "Run gnn_model.py and random_forest_model.py to enable ML."
            )

    @property
    def available(self) -> bool:
        return self.rf is not None

    # ── public entry point ────────────────────────────────────────────────────

    def score(
        self,
        faculty_name: str,
        room_number: str,
        day: str,
        slot: int,
        is_lab: bool,
        contact_hours: int,
        semester: int,
        current_load: int,
        course_name: Optional[str]   = None,
        room_type: Optional[str]     = None,
        room_capacity: Optional[int] = None,
        requires_consecutive_slots: bool = False,
        is_elective: bool            = False,
        section_name: Optional[str]  = None,
        program_code: Optional[str]  = None,
        current_load_today: int      = 0,
        max_daily: int               = 4,
        is_combined: bool            = False,
        working_days: Optional[list] = None,
    ) -> float:
        if self.available:
            return self._ml_score(
                faculty_name, room_number, day, slot,
                is_lab, contact_hours, semester, current_load,
                course_name=course_name, room_type=room_type,
                room_capacity=room_capacity,
                requires_consecutive_slots=requires_consecutive_slots,
                is_elective=is_elective, section_name=section_name,
                program_code=program_code,
                current_load_today=current_load_today,
                max_daily=max_daily,
                is_combined=is_combined, working_days=working_days,
            )
        return self._heuristic_score(day, slot, is_lab, current_load,
                                     self.max_hours_map.get(faculty_name, 18))

    # ── 114-dim feature vector → RF ──────────────────────────────────────────

    def _ml_score(
        self,
        faculty_name, room_number, day, slot,
        is_lab, contact_hours, semester, current_load,
        course_name=None, room_type=None, room_capacity=None,
        requires_consecutive_slots=False, is_elective=False,
        section_name=None, program_code=None,
        current_load_today: int = 0,
        max_daily: int = 4,
        is_combined: bool = False,
        working_days: Optional[list] = None,
    ) -> float:
        """
        Build a 114-dim feature vector and score via the trained RF model.
        Layout: fac_emb[32] + ts_emb[32] + rm_emb[32] + manual[18] = 114
        Must match random_forest_model.py exactly.
        """
        try:
            import numpy as np
            feat = self._build_feat(
                faculty_name, room_number, day, slot,
                is_lab, contact_hours, semester, current_load,
                course_name=course_name, room_type=room_type,
                room_capacity=room_capacity,
                requires_consecutive_slots=requires_consecutive_slots,
                is_elective=is_elective, section_name=section_name,
                program_code=program_code,
                current_load_today=current_load_today,
                max_daily=max_daily,
                is_combined=is_combined, working_days=working_days,
            ).reshape(1, -1)
            if self.scaler is not None:
                feat = self.scaler.transform(feat)
            return float(self.rf.predict_proba(feat)[0][1])

        except Exception as exc:
            log.warning(f"ML scoring failed ({exc}); using heuristic.")
            return self._heuristic_score(day, slot, is_lab, current_load,
                                         self.max_hours_map.get(faculty_name, 18))

    def _build_feat(
        self,
        faculty_name, room_number, day, slot,
        is_lab, contact_hours, semester, current_load,
        course_name=None, room_type=None, room_capacity=None,
        requires_consecutive_slots=False, is_elective=False,
        section_name=None, program_code=None,
        current_load_today=0, max_daily=4,
        is_combined=False, working_days=None,
    ):
        """Build a 114-dim feature vector (numpy array, not yet scaled)."""
        import numpy as np
        EMBED_DIM = 32
        ZERO = np.zeros(EMBED_DIM, dtype=np.float32)

        fac_emb = self.embeddings.get(f"FAC::{faculty_name}", ZERO)
        ts_emb  = self.embeddings.get(f"TSL::{DAY_FULL.get(day, day)[:3].upper()}_S{slot}", ZERO)
        rm_emb  = self.embeddings.get(f"RRM::{room_number}", ZERO)

        max_h    = self.max_hours_map.get(faculty_name, 18)
        day_full = DAY_FULL.get(day, day)

        load_remaining     = max(0.0, (max_h - current_load) / max(max_h, 1))
        actual_slots       = self.stats.get("fac_actual_slots", {}).get(faculty_name, set())
        is_known_slot      = 1.0 if (day_full, slot) in actual_slots else 0.0
        freq               = self.stats.get("fac_course_freq", {}).get((faculty_name, course_name or ""), 0)
        fac_max_freq       = self._fac_max_freq.get(faculty_name, 1)
        fac_course_affinity = freq / max(fac_max_freq, 1)
        slot_pop           = self.stats.get("slot_popularity", {}).get(slot, 0.5)
        day_pop            = self.stats.get("day_popularity", {}).get(day_full, 0.5)
        is_lab_f           = float(is_lab)
        is_consecutive_lab = 1.0 if requires_consecutive_slots else 0.0
        is_morning         = 1.0 if slot <= 3 else 0.0
        is_post_lunch      = 1.0 if slot >= 5 else 0.0
        sem_norm           = float(semester) / 8.0
        contact_norm       = float(contact_hours) / 8.0
        breadth            = self.stats.get("fac_course_count", {}).get(faculty_name, 1)
        breadth_norm       = min(breadth / 10.0, 1.0)
        fac_today_ratio    = float(current_load_today) / max(float(max_daily), 1.0)
        adj_left           = self.stats.get("slot_popularity", {}).get(slot - 1, 0.5)
        adj_right          = self.stats.get("slot_popularity", {}).get(slot + 1, 0.5)
        slot_adjacent_density = (adj_left + adj_right) / 2.0
        near_weekly_cap    = 1.0 if current_load >= max_h * 0.85 else 0.0
        overload_severity  = max(0.0, (current_load - max_h) / max(max_h, 1))
        combined_val       = 1.0 if is_combined else 0.0
        _wd                = working_days if working_days is not None else list(DAY_FULL.values())
        is_working_day_val = 1.0 if DAY_FULL.get(day, day) in _wd else 0.0

        manual = np.array([
            load_remaining, is_known_slot, fac_course_affinity, slot_pop,
            day_pop, is_lab_f, is_consecutive_lab, is_morning, is_post_lunch,
            sem_norm, contact_norm, breadth_norm, fac_today_ratio,
            slot_adjacent_density, near_weekly_cap, overload_severity,
            combined_val, is_working_day_val,
        ], dtype=np.float32)

        return np.concatenate([fac_emb, ts_emb, rm_emb, manual])

    def score_batch(self, param_list: list) -> list:
        """
        Score multiple candidates in one RF call.
        param_list: list of kwargs dicts for _build_feat().
        Returns list of float scores (same order).
        """
        if not self.available or not param_list:
            return [self._heuristic_score(
                p["day"], p["slot"], p.get("is_lab", False),
                p.get("current_load", 0), self.max_hours_map.get(p["faculty_name"], 18)
            ) for p in param_list]
        try:
            import numpy as np
            feats = np.stack([self._build_feat(**p) for p in param_list])
            if self.scaler is not None:
                feats = self.scaler.transform(feats)
            proba = self.rf.predict_proba(feats)[:, 1]
            return proba.tolist()
        except Exception as exc:
            log.warning(f"Batch ML scoring failed ({exc}); falling back to per-item heuristic.")
            return [self._heuristic_score(
                p["day"], p["slot"], p.get("is_lab", False),
                p.get("current_load", 0), self.max_hours_map.get(p["faculty_name"], 18)
            ) for p in param_list]

    # ── heuristic fallback ────────────────────────────────────────────────────

    def _heuristic_score(
        self, day: str, slot: int, is_lab: bool,
        current_load: int, max_load: int = 18,
    ) -> float:
        score = 0.5

        if is_lab:
            if slot in (1, 2):  score += 0.20
            elif slot == 3:     score += 0.10
            elif slot >= 5:     score -= 0.10
        else:
            if slot in (2, 3):  score += 0.08
            elif slot == 1:     score += 0.04
            elif slot >= 5:     score += 0.02

        if day in ("TUE", "WED", "THU"):  score += 0.05
        elif day in ("MON", "FRI"):       score -= 0.02

        ratio = current_load / max(max_load, 1)
        if ratio > 0.9:    score -= 0.30
        elif ratio > 0.7:  score -= 0.10

        return max(0.0, min(1.0, score))


# ═════════════════════════════════════════════════════════════════════════════
# CONSTRAINT TRACKER
# In-memory O(1) conflict detection. No DB queries inside the loop.
# ═════════════════════════════════════════════════════════════════════════════

class ConstraintTracker:
    """
    Tracks every assignment made during a scheduling run.
    assign() / unassign() implement atomic pair operations for labs.
    """

    def __init__(self):
        self._faculty_busy   = defaultdict(set)   # (day,slot) → {fac_id,...}
        self._room_busy      = defaultdict(set)   # (day,slot) → {room_id,...}
        self._group_busy     = defaultdict(set)   # (day,slot) → {group_id,...}
        self._fac_day        = defaultdict(lambda: defaultdict(int))
        self._fac_week       = defaultdict(int)
        self._fac_slots      = defaultdict(lambda: defaultdict(list))
        self._group_day      = defaultdict(lambda: defaultdict(int))
        self._group_lab_days = defaultdict(set)
        self.section_room_count = defaultdict(lambda: defaultdict(int))

    # ── hard constraint check ─────────────────────────────────────────────────

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
        """Atomically check both slots of a consecutive lab pair."""
        ok, reason = self.check(fac_id, room_id, group_id, day, s1,
                                max_daily, max_weekly, max_consec)
        if not ok:
            return False, reason
        self.assign(fac_id, room_id, group_id, day, s1)
        ok2, reason2 = self.check(fac_id, room_id, group_id, day, s2,
                                   max_daily, max_weekly, max_consec)
        self.unassign(fac_id, room_id, group_id, day, s1)
        return ok2, reason2

    # ── assignment / rollback ─────────────────────────────────────────────────

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

    # ── query helpers ─────────────────────────────────────────────────────────

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


# ═════════════════════════════════════════════════════════════════════════════
# SCHEDULER ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class SchedulerEngine:
    """One instance per scheduling run."""

    def __init__(self, timetable_id: int):
        self.timetable_id = timetable_id
        self.timetable    = (
            Timetable.objects
            .select_related("term", "term__program")
            .get(pk=timetable_id)
        )
        self.term   = self.timetable.term
        self.ml     = MLScorer()
        self.tracker = ConstraintTracker()
        self.config  = SchedulerConfig.get()

        self.slot_map:     dict = {}
        self.slot_id_to_key: dict = {}
        self.lab_rooms:    list = []
        self.theory_rooms: list = []
        self.faculty_meta: dict = {}
        self.offerings:    list = []

        self.pending_saves:         list  = []
        self.unscheduled:           list  = []
        self.unscheduled_offerings: list  = []
        self.rejection_reasons             = defaultdict(Counter)

        # Cache: ML-ranked faculty fallback keyed by course_id
        # Built once per course per run; reused by repair pass.
        self._ml_faculty_cache: dict[int, list] = {}

        # Room sort key (built in _load, used wherever room pool is sliced)
        self._room_sort_key = None

    # ── internal helpers ──────────────────────────────────────────────────────

    def _label(self, offering: CourseOffering, prefix: str) -> str:
        return f"{prefix} {offering.course.code} ({offering.student_group.name})"

    def _top_reasons(self, label: str, limit: int = 3) -> list[dict]:
        return [
            {"reason": r, "count": c}
            for r, c in self.rejection_reasons.get(label, Counter()).most_common(limit)
        ]

    # ═════════════════════════════════════════════════════════════════════════
    # PHASE 1: LOAD
    # ═════════════════════════════════════════════════════════════════════════

    def _load(self):
        log.info(f"Loading data for term: {self.term}")

        # ── timeslots ─────────────────────────────────────────────────────────
        if TimeSlot.objects.count() == 0:
            log.info("  No timeslots found — auto-seeding standard grid")
            from datetime import time as dt_time
            _SLOT_TIMES = [
                (1,  dt_time(9, 40),  dt_time(10, 35), False),
                (2,  dt_time(10, 35), dt_time(11, 30), False),
                (3,  dt_time(11, 30), dt_time(12, 25), False),
                (4,  dt_time(12, 25), dt_time(13, 20), False),
                (99, dt_time(13, 20), dt_time(14, 15), True),
                (5,  dt_time(14, 15), dt_time(15, 10), False),
                (6,  dt_time(15, 10), dt_time(16, 5),  False),
            ]
            bulk = [
                TimeSlot(day=d, slot_number=sn, start_time=st, end_time=et, is_lunch=il)
                for d in DAYS
                for sn, st, et, il in _SLOT_TIMES
            ]
            TimeSlot.objects.bulk_create(bulk, ignore_conflicts=True)
            log.info(f"  Seeded {len(bulk)} timeslots")

        for ts in TimeSlot.objects.filter(is_lunch=False).order_by("slot_number"):
            self.slot_map[(ts.day, ts.slot_number)] = ts
        self.slot_id_to_key = {ts.id: key for key, ts in self.slot_map.items()}
        log.info(f"  Slots loaded: {len(self.slot_map)}")

        # ── rooms: build program-affinity sort key ────────────────────────────
        rooms = list(
            Room.objects.filter(is_active=True)
            .select_related("building")
            .order_by("-priority_weight", "room_number")
        )

        program_id  = self.term.program_id
        prog_maps   = list(
            ProgramRoomMapping.objects
            .filter(program_id=program_id)
            .select_related("room__building")
            .order_by("-priority_weight")
        )
        prog_room_ids      = {m.room_id: m.priority_weight for m in prog_maps}
        prog_room_building = None
        prog_room_floor    = None

        if prog_maps:
            from collections import Counter as _C
            bld_votes   = _C(m.room.building_id for m in prog_maps)
            dominant_bld = bld_votes.most_common(1)[0][0]
            flr_votes   = _C(
                m.room.floor for m in prog_maps
                if m.room.building_id == dominant_bld
            )
            prog_room_building = dominant_bld
            prog_room_floor    = flr_votes.most_common(1)[0][0] if flr_votes else None
            log.info(
                f"  Program room preference: building_id={prog_room_building}, "
                f"floor={prog_room_floor}, {len(prog_room_ids)} mapped rooms"
            )

        def _room_sort_key(r):
            """
            Priority tiers (ascending sort value = higher priority):
            1. Explicitly mapped to this program   (higher mapping weight = better)
            2. Same building as program's dominant building
            3. Same floor as dominant floor
            4. Room's own priority_weight
            5. Capacity descending (larger rooms before tiny ones)
            6. Room number (alphabetical tiebreak)
            """
            in_prog   = prog_room_ids.get(r.id, 0)
            same_bldg = 1 if (prog_room_building and r.building_id == prog_room_building) else 0
            same_flr  = 1 if (prog_room_floor is not None and r.floor == prog_room_floor) else 0
            return (
                -in_prog,
                -same_bldg,
                -same_flr,
                -r.priority_weight,
                -r.capacity,
                r.room_number,
            )

        self._room_sort_key = _room_sort_key
        self.lab_rooms    = sorted([r for r in rooms if r.room_type == "LAB"],    key=_room_sort_key)
        self.theory_rooms = sorted([r for r in rooms if r.room_type == "THEORY"], key=_room_sort_key)

        log.info(f"  Rooms: {len(self.lab_rooms)} labs, {len(self.theory_rooms)} theory")
        if self.theory_rooms:
            top3 = [f"{r.building.code}-{r.room_number}" for r in self.theory_rooms[:3]]
            log.info(f"  Theory room priority order (top 3): {top3}")

        # ── faculty ───────────────────────────────────────────────────────────
        active_days = DAYS + (["SAT"] if self.config.allow_weekend_classes else [])

        for fac in Faculty.objects.filter(is_active=True).prefetch_related("availabilities"):
            avail_days:         set  = set()
            avail_slots_by_day: dict = defaultdict(set)

            if self.config.enforce_faculty_availability:
                for av in fac.availabilities.all():
                    avail_days.add(av.day)
                    for s in range(av.start_slot, av.end_slot + 1):
                        avail_slots_by_day[av.day].add(s)

            if not avail_days:
                avail_days = set(active_days)
                for d in active_days:
                    avail_slots_by_day[d] = set(TEACHING_SLOTS)

            max_daily  = min(fac.max_lectures_per_day, len(TEACHING_SLOTS))
            max_consec = min(fac.max_consecutive_lectures, max_daily)

            filtered: dict = {}
            for d, slots in avail_slots_by_day.items():
                clean = slots & set(TEACHING_SLOTS)
                if clean:
                    filtered[d] = clean
            for d in avail_days:
                if d not in filtered:
                    filtered[d] = set(TEACHING_SLOTS)

            self.faculty_meta[fac.id] = {
                "obj"        : fac,
                "avail_days" : avail_days,
                "avail_slots": filtered,
                "max_weekly" : fac.max_weekly_load,
                "max_daily"  : max_daily,
                "max_consec" : max_consec,
            }

        log.info(f"  Faculty loaded: {len(self.faculty_meta)}")

        # ── offerings ─────────────────────────────────────────────────────────
        # Skip PC/standard-theory offerings for combined groups (e.g. A+B).
        # Combined groups only need Lab (PR), Project (PRJ), AEC, and PE courses;
        # theory is already covered by the individual section offerings (A, B).
        COMBINED_ALLOWED_TYPES = {"PE"}

        # Build a map of all plain sections so we can derive working_days for
        # combined groups (A+B has empty working_days; we use the intersection
        # of its constituent sections so e.g. if A has WED off, A+B does too).
        all_sgs = {sg.name: sg for sg in StudentGroup.objects.filter(term=self.term)}
        for sg in all_sgs.values():
            if "+" in sg.name and not sg.working_days:
                parts = sg.name.split("+")
                days_sets = [
                    set(all_sgs[p].working_days)
                    for p in parts
                    if p in all_sgs and all_sgs[p].working_days
                ]
                if days_sets:
                    intersection = days_sets[0].intersection(*days_sets[1:])
                    sg.working_days = sorted(intersection, key=lambda d: ["MON","TUE","WED","THU","FRI","SAT"].index(d))

        # Build combined→individual section mapping for blocking
        # e.g. A+B → [id_of_A, id_of_B]
        self._combined_to_individual = {}
        for sg in all_sgs.values():
            if "+" in sg.name:
                parts = sg.name.split("+")
                individual_ids = [
                    all_sgs[p].id for p in parts if p in all_sgs
                ]
                if individual_ids:
                    self._combined_to_individual[sg.id] = individual_ids
        if self._combined_to_individual:
            log.info(
                f"  Combined→individual mapping: "
                f"{len(self._combined_to_individual)} combined groups"
            )

        self.offerings = [
            o for o in
            CourseOffering.objects
            .filter(student_group__term=self.term)
            .select_related("course", "student_group", "assigned_faculty")
            if "+" not in o.student_group.name
            or o.course.course_type in COMBINED_ALLOWED_TYPES
        ]
        # Attach the corrected working_days to each offering's student_group in memory
        for o in self.offerings:
            if o.student_group.name in all_sgs:
                o.student_group.working_days = all_sgs[o.student_group.name].working_days

        # ── Remove redundant overlapping offerings ────────────────────────────
        # When both combined (e.g. A+B) AND individual (A, B) offerings exist
        # for the same course:
        #   PE courses: KEEP combined (A+B), REMOVE individual → schedule view
        #               shows A+B allocations for all sections automatically.
        #   Non-PE:     KEEP individual, REMOVE combined → avoids double-scheduling.
        from collections import defaultdict as _dd
        individual_by_course = _dd(set)
        combined_by_course   = _dd(set)
        course_type_map      = {}
        for o in self.offerings:
            course_type_map[o.course_id] = o.course.course_type
            if "+" not in o.student_group.name:
                individual_by_course[o.course_id].add(o.id)
            else:
                combined_by_course[o.course_id].add(o.id)

        redundant_ids = set()
        for cid in set(individual_by_course) & set(combined_by_course):
            if course_type_map.get(cid) == "PE":
                # PE: keep combined (A+B), remove individual (A, B)
                redundant_ids |= individual_by_course[cid]
            else:
                # Non-PE: keep individual, remove combined
                redundant_ids |= combined_by_course[cid]

        if redundant_ids:
            before = len(self.offerings)
            self.offerings = [o for o in self.offerings if o.id not in redundant_ids]
            log.info(
                f"  Removed {before - len(self.offerings)} redundant overlapping "
                f"offerings (PE→keep A+B, non-PE→keep individual)"
            )

        log.info(f"  Offerings loaded: {len(self.offerings)}")

    # ═════════════════════════════════════════════════════════════════════════
    # ML-RANKED FACULTY FALLBACK
    # Used when no FacultySubjectEligibility records exist for a course.
    # Result is cached per course_id for the duration of the run.
    # ═════════════════════════════════════════════════════════════════════════

    def _ml_rank_all_faculty(self, offering: CourseOffering) -> list:
        course = offering.course
        if course.id in self._ml_faculty_cache:
            return self._ml_faculty_cache[course.id]

        group  = offering.student_group
        is_lab = bool(course.requires_lab_room or course.requires_consecutive_slots)

        all_fac = list(Faculty.objects.filter(is_active=True))
        log.warning(
            f"No eligible faculty for {course.code}. "
            f"ML-ranking all {len(all_fac)} active faculty as fallback."
        )

        # Batch-score all faculty in one RF call
        at_caps  = []
        sp_rank  = []
        for fac in all_fac:
            meta       = self.faculty_meta.get(fac.id, {})
            cur_load   = self.tracker.faculty_week_load(fac.id)
            max_weekly = meta.get("max_weekly", fac.max_weekly_load or 18)
            today_load = self.tracker.faculty_day_load(fac.id, "WED")
            max_daily  = meta.get("max_daily", fac.max_lectures_per_day or 4)
            at_caps.append(cur_load >= max_weekly)
            sp_rank.append(dict(
                faculty_name               = fac.name,
                room_number                = "UNKNOWN",
                day                        = "WED",
                slot                       = 2,
                is_lab                     = is_lab,
                contact_hours              = offering.weekly_load or course.min_weekly_lectures,
                semester                   = self.term.semester,
                current_load               = cur_load,
                course_name                = course.name,
                room_type                  = "LAB" if is_lab else "THEORY",
                room_capacity              = 60,
                requires_consecutive_slots = bool(course.requires_consecutive_slots),
                is_elective                = course.course_type in {"OE", "PE"},
                section_name               = group.name,
                program_code               = getattr(self.term.program, "code", None),
                current_load_today         = today_load,
                max_daily                  = max_daily,
                is_combined                = bool(offering.combined_token),
                working_days               = group.working_days,
            ))

        scores_rank = self.ml.score_batch(sp_rank)
        scored = [(sc, at_cap, fac) for sc, at_cap, fac in zip(scores_rank, at_caps, all_fac)]

        # Higher score first; ties broken by not-at-cap, then insertion order
        scored.sort(key=lambda x: (-x[0], x[1]))
        result = [fac for _, _, fac in scored]
        log.info(f"  ML ranking for {course.code}: top 3 = {[f.name for f in result[:3]]}")
        self._ml_faculty_cache[course.id] = result
        return result

    # ═════════════════════════════════════════════════════════════════════════
    # ELIGIBLE FACULTY
    # ═════════════════════════════════════════════════════════════════════════

    def _eligible_faculty(self, offering: CourseOffering) -> list:
        """
        Return faculty eligible for this offering, priority-sorted.

        Step 1: PR auto-faculty  — derive from theory offering's assigned faculty
        Step 2: admin-assigned   — always position 0
        Step 3: FacultySubjectEligibility (priority_weight desc)
        Step 4: ML all-faculty fallback (cached per course)
        Step 5: filter out faculty at weekly cap
        Step 6: senior priority  — PVC/DEAN/HOD bubble up (assigned stays at 0)
        """
        result = []

        # ── Step 1: PR auto-faculty ───────────────────────────────────────────
        # When a lab offering has no admin-assigned faculty, inherit the faculty
        # from the matching theory offering of the same section (e.g.
        # "Python Programming Lab" → look for "Python Programming").
        if offering.course.course_type == "PR" and not offering.assigned_faculty:
            raw_name = offering.course.name
            # Strip common lab suffix variants to get theory name
            theory_name = (
                raw_name
                .replace(" Lab", "").replace(" lab", "")
                .replace("Lab ", "").replace("lab ", "")
                .replace("Lab", "").replace("lab", "")
                .strip()
            )
            for o in self.offerings:
                if (
                    o.course.course_type != "PR"
                    and theory_name.lower() in o.course.name.lower()
                    and o.student_group_id == offering.student_group_id
                    and o.assigned_faculty
                ):
                    result = [o.assigned_faculty]
                    log.debug(
                        f"  PR auto-faculty: {offering.course.code} ← "
                        f"{o.assigned_faculty.name} (theory={o.course.code})"
                    )
                    break

        # ── Step 2: Admin-assigned faculty always at position 0 ──────────────
        if offering.assigned_faculty and offering.assigned_faculty not in result:
            result = [offering.assigned_faculty] + result

        # ── Step 3: FacultySubjectEligibility records ─────────────────────────
        qs = (
            FacultySubjectEligibility.objects
            .filter(course=offering.course, faculty__is_active=True)
            .select_related("faculty")
            .order_by("-priority_weight")
        )
        for e in qs:
            if e.faculty not in result:
                result.append(e.faculty)

        # ── Step 4: ML all-faculty fallback (last resort) ─────────────────────
        if not result:
            result = self._ml_rank_all_faculty(offering)

        # ── Step 5: Filter out faculty at weekly cap ──────────────────────────
        result = [
            f for f in result
            if self.tracker.faculty_week_load(f.id)
            < self.faculty_meta.get(f.id, {}).get("max_weekly", 18)
        ]

        # ── Step 6: Senior priority ───────────────────────────────────────────
        if self.config.prioritize_senior_faculty and len(result) > 1:
            _senior = {"PVC", "DEAN", "HOD"}
            assigned = (
                result[0]
                if (result and offering.assigned_faculty
                    and result[0] == offering.assigned_faculty)
                else None
            )
            rest = result[1:] if assigned else result
            rest.sort(key=lambda f: (0 if f.role in _senior else 1))
            result = ([assigned] + rest) if assigned else rest

        return result

    # ═════════════════════════════════════════════════════════════════════════
    # ROOM PICKER
    # ═════════════════════════════════════════════════════════════════════════

    def _pick_room(
        self,
        pool: list,
        group_id: int,
        day: str,
        slot: int,
        capacity_needed: int,
        extra_busy_slots: Optional[list] = None,
    ) -> Optional[Room]:
        """
        Pick the best available room from `pool` for (day, slot).

        Priority:
          1. Section's historically preferred room (affinity from this run)
          2. Walk pool in program-affinity order (already pre-sorted by _load)

        `extra_busy_slots` is used by lab pair checks (e.g., also block slot s2).
        """
        busy = set(self.tracker._room_busy.get((day, slot), set()))
        if extra_busy_slots:
            for extra_slot in extra_busy_slots:
                busy |= self.tracker._room_busy.get((day, extra_slot), set())

        pref_id = self.tracker.preferred_room_for_section(group_id)
        if pref_id:
            for r in pool:
                if r.id == pref_id and r.id not in busy and r.capacity >= capacity_needed:
                    return r

        for r in pool:
            if r.id not in busy and r.capacity >= capacity_needed:
                return r

        return None

    # ═════════════════════════════════════════════════════════════════════════
    # SCORING HELPER
    # ═════════════════════════════════════════════════════════════════════════

    def _score_params(
        self,
        fac: Faculty,
        day: str,
        slot: int,
        is_lab: bool,
        offering: CourseOffering,
        room: Optional[Room] = None,
    ) -> dict:
        """Build kwargs dict for MLScorer.score_batch() / score()."""
        course    = offering.course
        group     = offering.student_group
        meta      = self.faculty_meta.get(fac.id, {})
        today_ld  = self.tracker.faculty_day_load(fac.id, day)
        max_daily = meta.get("max_daily", 4)
        return dict(
            faculty_name               = fac.name,
            room_number                = str(room.room_number) if room else "UNKNOWN",
            day                        = day,
            slot                       = slot,
            is_lab                     = is_lab,
            contact_hours              = offering.weekly_load or course.min_weekly_lectures,
            semester                   = self.term.semester,
            current_load               = self.tracker.faculty_week_load(fac.id),
            course_name                = course.name,
            room_type                  = room.room_type if room else ("LAB" if is_lab else "THEORY"),
            room_capacity              = room.capacity  if room else 60,
            requires_consecutive_slots = bool(course.requires_consecutive_slots),
            is_elective                = course.course_type in {"OE", "PE"},
            section_name               = group.name,
            program_code               = getattr(self.term.program, "code", None),
            current_load_today         = today_ld,
            max_daily                  = max_daily,
            is_combined                = bool(offering.combined_token),
            working_days               = group.working_days,
        )

    def _score(
        self,
        fac: Faculty,
        day: str,
        slot: int,
        is_lab: bool,
        offering: CourseOffering,
        room: Optional[Room] = None,
    ) -> float:
        """Score a single (faculty, day, slot) candidate."""
        return self.ml.score(**self._score_params(fac, day, slot, is_lab, offering, room))

    # ═════════════════════════════════════════════════════════════════════════
    # COMBINED-AWARE ASSIGN
    # When assigning a combined section (e.g. A+B), also block constituent
    # individual sections (A, B) so they don't get overlapping theory classes.
    # ═════════════════════════════════════════════════════════════════════════

    def _assign_combined(self, fac_id, room_id, group_id, day, slot):
        """Assign and also block constituent sections of combined groups."""
        self.tracker.assign(fac_id, room_id, group_id, day, slot)
        for individual_id in self._combined_to_individual.get(group_id, []):
            self.tracker._group_busy[(day, slot)].add(individual_id)
            self.tracker._group_day[individual_id][day] += 1

    def _unassign_combined(self, fac_id, room_id, group_id, day, slot):
        """Unassign and also unblock constituent sections."""
        self.tracker.unassign(fac_id, room_id, group_id, day, slot)
        for individual_id in self._combined_to_individual.get(group_id, []):
            self.tracker._group_busy[(day, slot)].discard(individual_id)
            self.tracker._group_day[individual_id][day] = max(
                0, self.tracker._group_day[individual_id][day] - 1
            )

    def _assign_pe_slot(self, pe_assignments, day, slot):
        """Assign multiple PE options at the same (day, slot).
        pe_assignments: list of (fac_id, room_id, group_id) tuples.
        Groups are counted ONCE even if multiple options use the same group.
        """
        groups_done = set()
        for fac_id, room_id, group_id in pe_assignments:
            # Faculty busy (each PE option has different faculty)
            if fac_id:
                self.tracker._faculty_busy[(day, slot)].add(fac_id)
                self.tracker._fac_day[fac_id][day] += 1
                self.tracker._fac_week[fac_id] += 1
                self.tracker._fac_slots[fac_id][day].append(slot)
            # Room busy (each PE option gets a different room)
            self.tracker._room_busy[(day, slot)].add(room_id)
            # Group busy — count ONCE per group, not per PE option
            if group_id not in groups_done:
                self.tracker._group_busy[(day, slot)].add(group_id)
                self.tracker._group_day[group_id][day] += 1
                groups_done.add(group_id)
                # Also mark constituent individual sections
                for ind_id in self._combined_to_individual.get(group_id, []):
                    if ind_id not in groups_done:
                        self.tracker._group_busy[(day, slot)].add(ind_id)
                        self.tracker._group_day[ind_id][day] += 1
                        groups_done.add(ind_id)

    # ═════════════════════════════════════════════════════════════════════════
    # PHASE 2: LABS  (scarcest resource first, section-by-section)
    # ═════════════════════════════════════════════════════════════════════════

    def _schedule_labs(self, lab_offerings: list):
        """
        Phase 1: Scheduling Laboratory sessions (PR) and Projects (PRJ).
        Labs are given the highest priority to schedule because they require 
        consecutive double-slots, specific lab rooms, and only one lab per day 
        for any group.
        """
        """
        Labs need 2 consecutive slots + lab room — schedule them before theory.

        CRITICAL: Process section-by-section (all of section A before section B)
        to prevent competing for the same lab room simultaneously.
        """
        log.info(f"LAB PHASE: {len(lab_offerings)} lab offerings")

        # Group by student_group so we process one section fully before the next
        by_group: dict = defaultdict(list)
        for o in lab_offerings:
            if o.course.min_weekly_lectures > 0:
                by_group[o.student_group_id].append(o)

        for group_id, group_offerings in by_group.items():
            for offering in group_offerings:
                self._schedule_one_lab(offering)

    def _schedule_one_lab(self, offering: CourseOffering):
        course    = offering.course
        group     = offering.student_group
        group_id  = group.id

        # Determine pool (lab room required vs theory-room-based practical)
        pool = self.lab_rooms if course.requires_lab_room else self.theory_rooms

        # Auto-detect split: group name contains G1/G2, or no single room fits
        is_split = (
            "G1" in group.name.upper()
            or "G2" in group.name.upper()
            or "SPLIT" in (group.description or "").upper()
        )
        if not is_split:
            if pool and all(r.capacity < group.strength for r in pool):
                log.info(f"  LAB {course.code} ({group.name}): auto-split (no room fits full strength)")
                is_split = True

        eligible  = self._eligible_faculty(offering)
        scheduled = False

        # ── build candidates: batch-score per (fac, day, pair) ───────────────
        raw       = []   # (day, s1, s2, fac, meta)
        score_params = []
        for fac in eligible:
            meta = self.faculty_meta.get(fac.id)
            if not meta:
                continue
            for day in meta["avail_days"]:
                if group.working_days and day not in group.working_days:
                    continue
                if self.tracker.group_has_lab_today(group_id, day):
                    continue
                if self.tracker.group_day_load(group_id, day) >= len(TEACHING_SLOTS) - 1:
                    continue
                avail = meta["avail_slots"].get(day, set())
                for s1, s2 in VALID_CONSECUTIVE_PAIRS:
                    if s1 not in avail or s2 not in avail:
                        continue
                    raw.append((day, s1, s2, fac, meta))
                    score_params.append(self._score_params(fac, day, s1, True, offering))

        scores = self.ml.score_batch(score_params) if score_params else []
        candidates = [
            (sc, tb, day, s1, s2, fac, meta)
            for tb, ((day, s1, s2, fac, meta), sc) in enumerate(zip(raw, scores))
        ]
        candidates.sort(reverse=True)

        if not is_split:
            # ── whole-section lab ─────────────────────────────────────────────
            for sc, _tb, day, s1, s2, fac, meta in candidates:
                if scheduled:
                    break
                room = self._pick_room(pool, group_id, day, s1, group.strength,
                                       extra_busy_slots=[s2])
                if not room:
                    continue
                ok, _ = self.tracker.check_pair(
                    fac.id, room.id, group_id, day, s1, s2,
                    meta["max_daily"], meta["max_weekly"], meta["max_consec"],
                )
                if not ok:
                    continue

                self._assign_combined(fac.id, room.id, group_id, day, s1)
                self._assign_combined(fac.id, room.id, group_id, day, s2)
                self.tracker.mark_group_lab_day(group_id, day)

                for slot in (s1, s2):
                    self.pending_saves.append({
                        "offering_id"     : offering.id,
                        "student_group_id": group_id,
                        "faculty_id"      : fac.id,
                        "room_id"         : room.id,
                        "timeslot_id"     : self.slot_map[(day, slot)].id,
                        "score"           : sc,
                    })
                log.info(
                    f"  LAB ✓ {course.code} | {fac.name} | "
                    f"Room {room.room_number} ({room.building.code}) | "
                    f"{day} S{s1}+S{s2} | score={sc:.3f}"
                )
                scheduled = True

        else:
            # ── G1/G2 split: need 2 rooms free at both slots ─────────────────
            half = group.strength // 2
            for sc, _tb, day, s1, s2, fac, meta in candidates:
                if scheduled:
                    break
                busy_s1 = self.tracker._room_busy.get((day, s1), set())
                busy_s2 = self.tracker._room_busy.get((day, s2), set())
                free = [
                    r for r in pool
                    if r.capacity >= half
                    and r.id not in busy_s1
                    and r.id not in busy_s2
                ]
                if len(free) < 2:
                    continue
                ok, _ = self.tracker.check_pair(
                    fac.id, free[0].id, group_id, day, s1, s2,
                    meta["max_daily"], meta["max_weekly"], meta["max_consec"],
                )
                if not ok:
                    continue

                room_g1, room_g2 = free[0], free[1]
                for slot in (s1, s2):
                    self._assign_combined(fac.id, room_g1.id, group_id, day, slot)
                    # Mark g2 as busy without creating an allocation record
                    self.tracker._room_busy[(day, slot)].add(room_g2.id)
                    self.pending_saves.append({
                        "offering_id"     : offering.id,
                        "student_group_id": group_id,
                        "faculty_id"      : fac.id,
                        "room_id"         : room_g1.id,
                        "timeslot_id"     : self.slot_map[(day, slot)].id,
                        "score"           : sc,
                    })
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

    # ═════════════════════════════════════════════════════════════════════════
    # PHASE 3: THEORY
    # Sub-phases: 3a electives → 3b combined → 3c standard → 3d repair
    # ═════════════════════════════════════════════════════════════════════════

    def _schedule_theory(self, theory_offerings: list):
        """
        Phase 2: Scheduling Theory (PC, BSC, ESC, etc).
        Theory subjects are scheduled one slot at a time. The system tries to spread
        them evenly across the working days to prevent students or faculty from 
        being overloaded on a single day.
        """
        log.info(f"THEORY PHASE: {len(theory_offerings)} theory offerings")
        theory_offerings.sort(key=lambda o: -o.course.priority)

        # ── PRJ (Project Work) — consecutive slots in theory rooms ────────────
        # PRJ requires 2 consecutive slots but uses theory (not lab) rooms.
        # Reuse _schedule_one_lab() which already handles the non-lab pool case.
        prj: list   = [o for o in theory_offerings if o.course.course_type == "PRJ"]
        rest: list  = [o for o in theory_offerings if o.course.course_type != "PRJ"]

        if prj:
            log.info(f"  PRJ sub-phase: {len(prj)} project offering(s)")
            for offering in prj:
                self._schedule_one_lab(offering)

        # ── separate elective groups from the rest ────────────────────────────
        elective_groups: dict = defaultdict(list)
        seen_in_elective: set = set()

        for o in rest:
            if o.elective_slot_group:
                elective_groups[o.elective_slot_group].append(o)
                seen_in_elective.add(o.id)

        # ── AUTO-MERGE PE GROUPS ──────────────────────────────────────────────
        # Per PDF: ALL PE options for the same program+semester must land on the
        # SAME (day, slot). Merge separate PE groups (PE1, PE2, …) and also
        # include any ungrouped PE offerings.
        pe_in_groups = []
        non_pe_groups = {}
        for gname, offs in elective_groups.items():
            if all(o.course.course_type == "PE" for o in offs):
                pe_in_groups.extend(offs)
            else:
                non_pe_groups[gname] = offs

        # Grab ungrouped PE offerings too
        ungrouped_pe = [
            o for o in rest
            if o.id not in seen_in_elective and o.course.course_type == "PE"
        ]
        all_pe = pe_in_groups + ungrouped_pe

        if all_pe:
            pe_by_term = defaultdict(list)
            for o in all_pe:
                pe_by_term[o.student_group.term_id].append(o)
            for term_id, offs in pe_by_term.items():
                grp_name = f"PE_auto_{term_id}"
                non_pe_groups[grp_name] = offs
                for o in offs:
                    seen_in_elective.add(o.id)
                n_courses = len({o.course_id for o in offs})
                log.info(
                    f"  PE auto-group '{grp_name}': {len(offs)} offerings, "
                    f"{n_courses} distinct options"
                )

        elective_groups = non_pe_groups
        remaining = [o for o in rest if o.id not in seen_in_elective]

        # ── separate combined vs standard from remaining ───────────────────────
        combined_map: dict = defaultdict(list)
        standard: list     = []

        for o in remaining:
            if o.combined_token and o.course.course_type != "PE":
                key = (o.course_id, o.combined_token)
                combined_map[key].append(o)
            else:
                standard.append(o)

        # course_days_used: prevents same course twice on same day (soft)
        course_days_used: dict = defaultdict(set)

        # ── 3a: parallel electives ────────────────────────────────────────────
        self._schedule_electives(elective_groups, course_days_used)

        # ── 3b: combined sections ─────────────────────────────────────────────
        for unit in combined_map.values():
            self._schedule_combined_unit(unit, course_days_used)

        # ── 3c: standard theory ───────────────────────────────────────────────
        for offering in standard:
            self._schedule_standard_unit([offering], course_days_used)

    # ── 3a: parallel electives ────────────────────────────────────────────────

    def _schedule_electives(self, elective_groups: dict, course_days_used: dict):
        """
        Phase 3: Scheduling Parallel Electives (PE).
        Electives are tricky because multiple courses (e.g. Cyber Security, IoT) 
        run at the exact same time for different sub-groups of students. 
        This block automatically merges all related options so they can be assigned 
        to the exact same day and slot, in multiple rooms, with different teachers.
        """
        """Schedule PE / elective groups so all options land on the SAME (day, slot).

        Key rules from the PDF:
          RULE 2 — OFF-DAY EXCLUSION (UNION): block days where ANY section has off.
          RULE 3 — SAME SLOT ALL OPTIONS: N options → N rooms at one (day, slot).
          RULE 4 — ALLOCATIONS: one row per option per offering.
          RULE 5 — FRONTEND: concatenated display.
        """
        for group_name, unit in elective_groups.items():
            # ── Group offerings by course_id (each course = one PE option) ─────
            by_course: dict = defaultdict(list)
            for o in unit:
                by_course[o.course_id].append(o)

            n_options  = len(by_course)
            needed     = max(o.course.min_weekly_lectures for o in unit)
            all_gids   = {o.student_group_id for o in unit}
            opt_names  = [offs[0].course.code for offs in by_course.values()]

            log.info(
                f"  Elective group {group_name!r}: {n_options} options "
                f"({', '.join(opt_names)}), {len(unit)} offerings, "
                f"need {needed} sessions"
            )

            # ── RULE 2: OFF-DAY EXCLUSION (UNION rule) ─────────────────────────
            blocked_days = set()
            for o in unit:
                sg = o.student_group
                if sg.working_days:
                    blocked_days |= ({"MON","TUE","WED","THU","FRI"} - set(sg.working_days))
            # Also check constituent sections for combined groups
            # Build a quick lookup of individual section working_days
            ind_working_days = {}
            for o in getattr(self, 'offerings', []):
                if "+" not in o.student_group.name and o.student_group.working_days:
                    ind_working_days[o.student_group_id] = o.student_group.working_days
            for gid in list(all_gids):
                for ind_id in self._combined_to_individual.get(gid, []):
                    wdays = ind_working_days.get(ind_id)
                    if wdays:
                        blocked_days |= ({"MON","TUE","WED","THU","FRI"} - set(wdays))
            eligible_days = [d for d in DAYS if d not in blocked_days]
            if blocked_days:
                log.info(
                    f"    Off-day UNION rule: blocked={blocked_days}, "
                    f"eligible={eligible_days}"
                )

            # ── Collect unique faculty across options ──────────────────────────
            option_faculty = {}  # course_id → faculty_id
            for cid, offerings in by_course.items():
                fac = offerings[0].assigned_faculty
                option_faculty[cid] = fac.id if fac else None

            scheduled_count = 0
            for _pass in range(needed):
                slot_candidates = []

                for day in eligible_days:
                    # No course in this group should already be on this day
                    if any(day in course_days_used[cid] for cid in by_course):
                        continue
                    for slot in TEACHING_SLOTS:
                        if (day, slot) not in self.slot_map:
                            continue
                        # All groups must be free
                        if any(
                            not self.tracker.is_group_free(gid, day, slot)
                            for gid in all_gids
                        ):
                            continue
                        # Each option's faculty must be free
                        fac_ok = True
                        for cid, fid in option_faculty.items():
                            if not fid:
                                continue
                            m = self.faculty_meta.get(fid)
                            if not m:
                                continue
                            ok, _ = self.tracker.check(
                                fid, None, None, day, slot,
                                m["max_daily"], m["max_weekly"], 99,
                            )
                            if not ok:
                                fac_ok = False
                                break
                        if not fac_ok:
                            continue
                        # Need n_options rooms (one per PE option)
                        busy = self.tracker._room_busy.get((day, slot), set())
                        free = [r for r in self.theory_rooms if r.id not in busy]
                        if len(free) < n_options:
                            continue
                        sc = 0.5 + (0.1 if slot <= 3 else 0.0)
                        slot_candidates.append((sc, day, slot))

                slot_candidates.sort(reverse=True)
                placed = False

                for sc, day, slot in slot_candidates:
                    if placed:
                        break
                    busy = self.tracker._room_busy.get((day, slot), set())
                    free = [r for r in self.theory_rooms if r.id not in busy]
                    if len(free) < n_options:
                        continue

                    # ── Place all PE options at this (day, slot) ───────────────
                    pe_assignments = []
                    for idx, (cid, offerings) in enumerate(by_course.items()):
                        room   = free[idx]
                        fac_id = option_faculty[cid]
                        for o in offerings:
                            pe_assignments.append((fac_id, room.id, o.student_group_id))
                            self.pending_saves.append({
                                "offering_id"     : o.id,
                                "student_group_id": o.student_group_id,
                                "faculty_id"      : fac_id,
                                "room_id"         : room.id,
                                "timeslot_id"     : self.slot_map[(day, slot)].id,
                                "score"           : sc,
                                "is_pe"           : True,
                            })
                        course_days_used[cid].add(day)

                    # Batch-mark in tracker (groups counted ONCE)
                    self._assign_pe_slot(pe_assignments, day, slot)

                    placed = True
                    scheduled_count += 1
                    log.info(
                        f"    Elective {group_name!r} pass {_pass+1} done "
                        f"{day} S{slot} ({n_options} options)"
                    )

                if not placed:
                    log.warning(
                        f"    Elective {group_name!r} pass {_pass+1} "
                        f"-- no valid slot found"
                    )

    # ── 3b: combined sections ─────────────────────────────────────────────────

    def _schedule_combined_unit(self, unit: list, course_days_used: dict):
        """
        All offerings in `unit` share the same (day, slot, room, faculty).
        Room capacity = sum of all section strengths.
        """
        offering       = unit[0]
        course         = offering.course
        needed         = course.min_weekly_lectures
        if needed == 0:
            return

        group_ids      = [o.student_group_id for o in unit]
        groups         = [o.student_group for o in unit]
        total_strength = sum(g.strength for g in groups)
        eligible       = self._eligible_faculty(offering)
        MAX_GRP_DAILY  = len(TEACHING_SLOTS)
        scheduled      = 0

        raw_comb = []
        sp_comb  = []
        for fac in eligible:
            meta = self.faculty_meta.get(fac.id)
            if not meta:
                continue
            for day in meta["avail_days"]:
                if day in course_days_used[course.id]:
                    continue
                if any(g.working_days and day not in g.working_days for g in groups):
                    continue
                if any(self.tracker.group_day_load(gid, day) >= MAX_GRP_DAILY
                       for gid in group_ids):
                    continue
                for slot in sorted(meta["avail_slots"].get(day, set())):
                    if (day, slot) not in self.slot_map:
                        continue
                    if any(not self.tracker.is_group_free(gid, day, slot)
                           for gid in group_ids):
                        continue
                    raw_comb.append((day, slot, fac, meta))
                    sp_comb.append(self._score_params(fac, day, slot, False, offering))

        scores_comb = self.ml.score_batch(sp_comb) if sp_comb else []
        candidates = [
            (sc, tb, day, slot, fac, meta)
            for tb, ((day, slot, fac, meta), sc) in enumerate(zip(raw_comb, scores_comb))
        ]
        candidates.sort(reverse=True)

        for sc, _tb, day, slot, fac, meta in candidates:
            if scheduled >= needed:
                break
            if day in course_days_used[course.id]:
                continue

            room = self._pick_room(self.theory_rooms, group_ids[0], day, slot, total_strength)
            if not room:
                continue

            ok, _ = self.tracker.check(
                fac.id, room.id, group_ids[0], day, slot,
                meta["max_daily"], meta["max_weekly"], meta["max_consec"],
            )
            if not ok:
                continue

            for gid in group_ids:
                self._assign_combined(fac.id, room.id, gid, day, slot)
            for o in unit:
                self.pending_saves.append({
                    "offering_id"     : o.id,
                    "student_group_id": o.student_group_id,
                    "faculty_id"      : fac.id,
                    "room_id"         : room.id,
                    "timeslot_id"     : self.slot_map[(day, slot)].id,
                    "score"           : sc,
                })
            scheduled += 1
            course_days_used[course.id].add(day)
            log.info(
                f"  COMBINED ✓ {course.code} | {fac.name} | "
                f"R{room.room_number} ({room.building.code}) | {day} S{slot} | score={sc:.3f}"
            )

        if scheduled < needed:
            msg = (
                f"THEORY {course.code} "
                f"({'+'.join(g.name for g in groups)}) "
                f"— only {scheduled}/{needed} sessions scheduled"
            )
            self.unscheduled_offerings.append(offering)
            self.unscheduled.append(msg)
            log.warning(f"  UNSCHEDULED: {msg}")

    # ── 3c: standard theory ───────────────────────────────────────────────────

    def _schedule_standard_unit(self, unit: list, course_days_used: dict):
        """
        Single offering (no combined_token).
        """
        offering      = unit[0]
        course        = offering.course
        needed        = course.min_weekly_lectures
        if needed == 0:
            return

        group         = offering.student_group
        group_id      = group.id
        eligible      = self._eligible_faculty(offering)
        MAX_GRP_DAILY = len(TEACHING_SLOTS)
        scheduled     = 0

        # Max sessions any single faculty takes of this course
        # (ceil(needed/2)) — allows load sharing when multiple are eligible
        max_per_fac = math.ceil(needed / 2) if len(eligible) > 1 else needed
        fac_session_count: dict = defaultdict(int)

        raw_std   = []
        sp_std    = []
        for fac in eligible:
            meta = self.faculty_meta.get(fac.id)
            if not meta:
                continue
            for day in meta["avail_days"]:
                if day in course_days_used[course.id]:
                    continue
                if group.working_days and day not in group.working_days:
                    continue
                if self.tracker.group_day_load(group_id, day) >= MAX_GRP_DAILY:
                    continue
                for slot in sorted(meta["avail_slots"].get(day, set())):
                    if (day, slot) not in self.slot_map:
                        continue
                    if not self.tracker.is_group_free(group_id, day, slot):
                        continue
                    raw_std.append((day, slot, fac, meta))
                    sp_std.append(self._score_params(fac, day, slot, False, offering))

        scores_std = self.ml.score_batch(sp_std) if sp_std else []
        candidates = [
            (sc, tb, day, slot, fac, meta)
            for tb, ((day, slot, fac, meta), sc) in enumerate(zip(raw_std, scores_std))
        ]
        candidates.sort(reverse=True)

        for sc, _tb, day, slot, fac, meta in candidates:
            if scheduled >= needed:
                break
            if day in course_days_used[course.id]:
                continue
            if fac_session_count[fac.id] >= max_per_fac:
                continue

            room = self._pick_room(self.theory_rooms, group_id, day, slot, group.strength)
            if not room:
                continue

            ok, _ = self.tracker.check(
                fac.id, room.id, group_id, day, slot,
                meta["max_daily"], meta["max_weekly"], meta["max_consec"],
            )
            if not ok:
                continue

            self.tracker.assign(fac.id, room.id, group_id, day, slot)
            self.pending_saves.append({
                "offering_id"     : offering.id,
                "student_group_id": group_id,
                "faculty_id"      : fac.id,
                "room_id"         : room.id,
                "timeslot_id"     : self.slot_map[(day, slot)].id,
                "score"           : sc,
            })
            scheduled += 1
            fac_session_count[fac.id] += 1
            course_days_used[course.id].add(day)
            log.info(
                f"  THEORY ✓ {course.code} | {fac.name} | "
                f"R{room.room_number} ({room.building.code}) | {day} S{slot} | score={sc:.3f}"
            )

        if scheduled < needed:
            msg = (
                f"THEORY {course.code} ({group.name}) "
                f"— only {scheduled}/{needed} sessions scheduled"
            )
            self.unscheduled_offerings.append(offering)
            self.unscheduled.append(msg)
            log.warning(f"  UNSCHEDULED: {msg}")

    # ═════════════════════════════════════════════════════════════════════════
    # PHASE 3d: REPAIR PASS
    # Retry unscheduled theory offerings with relaxed soft constraints:
    #   - allow same day (day-distribution relaxed)
    #   - try all 5 days even if outside avail_days
    # ALL hard constraints (busy/caps/consecutive) still enforced.
    # ═════════════════════════════════════════════════════════════════════════

    def _repair_unscheduled(self) -> list:
        """
        Phase 4: ML Repair / Fallback Pass.
        If the strict rules rejected some classes (running out of valid rooms or 
        faculty workloads maxed out), this pass intelligently re-attempts 
        scheduling them using machine learning priorities and relaxed constraints.
        """
        if not self.unscheduled_offerings:
            return []

        log.info(
            f"REPAIR PASS: {len(self.unscheduled_offerings)} unscheduled offering(s)"
        )
        fixed          = []
        MAX_GRP_DAILY  = len(TEACHING_SLOTS)

        for offering in self.unscheduled_offerings:
            course   = offering.course
            group    = offering.student_group
            group_id = group.id
            needed   = course.min_weekly_lectures

            already     = sum(1 for a in self.pending_saves if a["offering_id"] == offering.id)
            still_need  = needed - already
            if still_need <= 0:
                fixed.append(offering)
                continue

            eligible    = self._eligible_faculty(offering)
            sched_now   = 0

            raw_rep = []
            sp_rep  = []
            for fac in eligible:
                meta = self.faculty_meta.get(fac.id)
                if not meta:
                    continue
                # Relaxation: try ALL working days (still respect group's day-off)
                for day in DAYS:
                    if group.working_days and day not in group.working_days:
                        continue
                    avail = meta["avail_slots"].get(day, set(TEACHING_SLOTS))
                    for slot in sorted(avail):
                        if slot not in TEACHING_SLOTS:
                            continue
                        if (day, slot) not in self.slot_map:
                            continue
                        if not self.tracker.is_group_free(group_id, day, slot):
                            continue
                        raw_rep.append((day, slot, fac, meta))
                        sp_rep.append(self._score_params(fac, day, slot, False, offering))

            scores_rep = self.ml.score_batch(sp_rep) if sp_rep else []
            candidates = [
                (sc, tb, day, slot, fac, meta)
                for tb, ((day, slot, fac, meta), sc) in enumerate(zip(raw_rep, scores_rep))
            ]
            candidates.sort(reverse=True)

            for sc, _tb, day, slot, fac, meta in candidates:
                if sched_now >= still_need:
                    break
                if self.tracker.group_day_load(group_id, day) >= MAX_GRP_DAILY:
                    continue

                room = self._pick_room(self.theory_rooms, group_id, day, slot, group.strength)
                if not room:
                    continue

                ok, _ = self.tracker.check(
                    fac.id, room.id, group_id, day, slot,
                    meta["max_daily"], meta["max_weekly"], meta["max_consec"],
                )
                if not ok:
                    continue

                self.tracker.assign(fac.id, room.id, group_id, day, slot)
                self.pending_saves.append({
                    "offering_id"     : offering.id,
                    "student_group_id": group_id,
                    "faculty_id"      : fac.id,
                    "room_id"         : room.id,
                    "timeslot_id"     : self.slot_map[(day, slot)].id,
                    "score"           : sc,
                })
                sched_now += 1
                log.info(
                    f"  REPAIR ✓ {course.code} | {fac.name} | "
                    f"R{room.room_number} ({room.building.code}) | "
                    f"{day} S{slot} | score={sc:.3f}"
                )

            if sched_now >= still_need:
                fixed.append(offering)
                log.info(f"  REPAIR: {course.code} ({group.name}) fully resolved.")
            elif sched_now > 0:
                fixed.append(offering)
                log.info(
                    f"  REPAIR: {course.code} ({group.name}) "
                    f"partially resolved (+{sched_now} sessions)."
                )

        log.info(
            f"REPAIR PASS done: {len(fixed)}/{len(self.unscheduled_offerings)} "
            "offerings improved."
        )
        return fixed

    # ═════════════════════════════════════════════════════════════════════════
    # PHASE 3e: IDLE ROOM PASS — resource packing after labs
    # After labs are placed some rooms have free slots. Try to fill them with
    # still-unscheduled offerings. All 8 hard constraints remain enforced.
    # ═════════════════════════════════════════════════════════════════════════

    def _idle_room_pass(self):
        if not self.unscheduled_offerings:
            return

        log.info(f"IDLE ROOM PASS: {len(self.unscheduled_offerings)} unscheduled offering(s)")

        # Build free-slot inventory once: room_id → set of (day, slot)
        all_rooms   = self.lab_rooms + self.theory_rooms
        all_ds_keys = set(self.slot_map.keys())   # {(day, slot), ...}

        free_inventory: dict = defaultdict(set)
        for room in all_rooms:
            for ds in all_ds_keys:
                if room.id not in self.tracker._room_busy.get(ds, set()):
                    free_inventory[room.id].add(ds)

        recovered = []

        for offering in list(self.unscheduled_offerings):
            is_lab = offering.course.requires_lab_room
            pool   = self.lab_rooms if is_lab else self.theory_rooms

            eligible = self._eligible_faculty(offering)
            if not eligible:
                continue

            placed = False
            for room in pool:
                if placed:
                    break
                if room.capacity < offering.student_group.strength:
                    continue
                for (day, slot) in sorted(free_inventory[room.id]):
                    if placed:
                        break
                    if not self.tracker.is_group_free(
                        offering.student_group_id, day, slot
                    ):
                        continue
                    for fac in eligible:
                        meta = self.faculty_meta.get(fac.id)
                        if not meta:
                            continue
                        ok, _ = self.tracker.check(
                            fac.id, room.id, offering.student_group_id,
                            day, slot,
                            meta["max_daily"], meta["max_weekly"], meta["max_consec"],
                        )
                        if ok:
                            self.tracker.assign(
                                fac.id, room.id, offering.student_group_id, day, slot
                            )
                            self.pending_saves.append({
                                "offering_id"     : offering.id,
                                "student_group_id": offering.student_group_id,
                                "faculty_id"      : fac.id,
                                "room_id"         : room.id,
                                "timeslot_id"     : self.slot_map[(day, slot)].id,
                                "score"           : 0.40,
                            })
                            free_inventory[room.id].discard((day, slot))
                            recovered.append(offering)
                            log.info(
                                f"  IDLE ✓ {offering.course.code} | {fac.name} | "
                                f"R{room.room_number} | {day} S{slot}"
                            )
                            placed = True
                            break

        self.unscheduled_offerings = [
            o for o in self.unscheduled_offerings if o not in recovered
        ]
        if recovered:
            recovered_codes = {o.course.code for o in recovered}
            self.unscheduled = [
                msg for msg in self.unscheduled
                if not any(code in msg for code in recovered_codes)
            ]

        log.info(
            f"IDLE ROOM PASS done: {len(recovered)} recovered, "
            f"{len(self.unscheduled_offerings)} still unscheduled."
        )

    # ═════════════════════════════════════════════════════════════════════════
    # PHASE 4: ATOMIC DB SAVE
    # ═════════════════════════════════════════════════════════════════════════

    @transaction.atomic
    def _save(self) -> int:
        log.info(f"Writing {len(self.pending_saves)} allocations to DB...")

        # ── deduplicate ───────────────────────────────────────────────────────
        seen_fac_slot  = set()
        seen_room_slot = set()
        seen_grp_slot  = set()
        deduped        = []
        skipped        = 0

        for alloc in self.pending_saves:
            kf = (alloc["faculty_id"],       alloc["timeslot_id"])
            kr = (alloc["room_id"],           alloc["timeslot_id"])
            kg = (alloc["student_group_id"],  alloc["timeslot_id"])
            is_pe = alloc.get("is_pe", False)

            # PE electives: multiple options can share the same (group, slot).
            # Only enforce room+slot and faculty+slot uniqueness.
            if is_pe:
                if kr in seen_room_slot:
                    log.warning(
                        f"  PE Dedup-skip: room={alloc['room_id']} "
                        f"ts={alloc['timeslot_id']}"
                    )
                    skipped += 1
                    continue
                seen_room_slot.add(kr)
                if kf and alloc["faculty_id"]:
                    seen_fac_slot.add(kf)
                deduped.append(alloc)
            else:
                if kf in seen_fac_slot or kr in seen_room_slot or kg in seen_grp_slot:
                    log.warning(
                        f"  Dedup-skip: fac={alloc['faculty_id']} "
                        f"room={alloc['room_id']} grp={alloc['student_group_id']} "
                        f"ts={alloc['timeslot_id']}"
                    )
                    skipped += 1
                    continue
                seen_fac_slot.add(kf)
                seen_room_slot.add(kr)
                seen_grp_slot.add(kg)
                deduped.append(alloc)

        if skipped:
            log.warning(f"  Dedup removed {skipped} duplicate allocation(s).")

        objs = [
            LectureAllocation(
                timetable_id             = self.timetable_id,
                course_offering_id       = a["offering_id"],
                student_group_id         = a["student_group_id"],
                faculty_id               = a["faculty_id"],
                room_id                  = a["room_id"],
                timeslot_id              = a["timeslot_id"],
                hard_constraint_violated = False,
                soft_constraint_score    = round(float(a["score"]), 4),
            )
            for a in deduped
        ]

        # ── bulk create with per-record fallback ──────────────────────────────
        bulk_ok = False
        try:
            with transaction.atomic():
                LectureAllocation.objects.bulk_create(objs)
            bulk_ok = True
        except Exception as bulk_err:
            log.error(f"  bulk_create failed ({bulk_err}). Falling back to per-record save.")

        if not bulk_ok:
            saved_indices = []
            for i, (alloc, obj) in enumerate(zip(deduped, objs)):
                try:
                    with transaction.atomic():
                        obj.pk = None
                        obj.save()
                    saved_indices.append(i)
                except Exception as row_err:
                    log.warning(
                        f"  Skipped: fac={obj.faculty_id} "
                        f"room={obj.room_id} ts={obj.timeslot_id}: {row_err}"
                    )
            deduped = [deduped[i] for i in saved_indices]

        created = len(deduped)

        if deduped:
            avg = sum(a["score"] for a in deduped) / len(deduped)
            self.timetable.total_constraint_score = round(avg, 4)
            self.timetable.save(update_fields=["total_constraint_score"])

        log.info(f"  Saved {created} allocations.")
        return created

    # ═════════════════════════════════════════════════════════════════════════
    # PUBLIC ENTRY POINT
    # ═════════════════════════════════════════════════════════════════════════

    def run(self) -> dict:
        """
        Main Engine Entry Point.
        This function handles the sequence of generating a timetable:
        1. Setup & load data
        2. Schedule strict classes (Labs)
        3. Schedule standard classes (Theory)
        4. Schedule parallel batches (Electives)
        5. Repair any missed classes
        6. Fill in free rooms
        7. Save the whole timetable to the database.
        """
        """
        Execute the full scheduling pipeline and return a summary dict.
        Return format matches what scheduler/views.py expects exactly.
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
                "timetable_id": self.timetable_id,
                "allocations" : 0,
                "avg_score"   : 0.0,
                "unscheduled" : [],
                "unscheduled_reasons": {},
                "ml_used"     : self.ml.available,
            }

        # Split into lab (PR only) and theory offerings.
        # PRJ (project work) needs consecutive slots but uses THEORY rooms —
        # it goes into theory_offerings so it benefits from the lower-priority
        # scheduling pass after labs have been placed.
        lab_offerings    = [
            o for o in self.offerings if o.course.requires_lab_room
        ]
        theory_offerings = [
            o for o in self.offerings if not o.course.requires_lab_room
        ]

        log.info(
            f"Offerings split: {len(lab_offerings)} labs (PR), "
            f"{len(theory_offerings)} theory (incl. PRJ)"
        )

        # Phase 2 — labs (section-by-section, scarcest first)
        if lab_offerings:
            self._schedule_labs(lab_offerings)

        # Phase 3 — theory (electives → combined → standard)
        if theory_offerings:
            self._schedule_theory(theory_offerings)

        # Phase 3d — repair pass
        if self.unscheduled_offerings:
            fixed = self._repair_unscheduled()
            if fixed:
                fixed_codes = {o.course.code for o in fixed}
                # Remove repaired entries from unscheduled list
                self.unscheduled = [
                    msg for msg in self.unscheduled
                    if not any(code in msg for code in fixed_codes)
                ]
                self.unscheduled_offerings = [
                    o for o in self.unscheduled_offerings
                    if o not in fixed
                ]

        # Phase 3e — idle room pass (pack free lab-room slots)
        self._idle_room_pass()

        # Phase 4 — save
        try:
            saved = self._save()
        except Exception as exc:
            log.error(f"DB save failed: {exc}")
            return {
                "status"      : "failed",
                "reason"      : str(exc),
                "timetable_id": self.timetable_id,
                "allocations" : 0,
                "avg_score"   : 0.0,
                "unscheduled" : self.unscheduled,
                "unscheduled_reasons": {},
                "ml_used"     : self.ml.available,
            }

        status = "success" if not self.unscheduled else "partial"

        result = {
            "status"      : status,
            "timetable_id": self.timetable_id,
            "allocations" : saved,
            "saved"       : saved,
            "avg_score"   : self.timetable.total_constraint_score,
            "unscheduled" : self.unscheduled,
            "unscheduled_reasons": {
                msg.split(" — ")[0]: self._top_reasons(msg.split(" — ")[0])
                for msg in self.unscheduled
            },
            "ml_used"     : self.ml.available,
            "warnings"    : self.unscheduled,   # alias for views that check 'warnings'
        }

        log.info(
            f"Scheduler done — status={status}, "
            f"saved={saved}, unscheduled={len(self.unscheduled)}"
        )
        return result
