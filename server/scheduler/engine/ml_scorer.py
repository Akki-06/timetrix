"""
ML scoring wrapper: GNN embeddings + Random Forest.

Verbatim move from scheduler_engine.py. No logic changes.
"""
import logging
import pickle
from typing import Optional

from scheduler.engine.constants import (
    DAY_FULL, EMBED_PATH, RF_MODEL_PATH, RF_META_PATH,
)

log = logging.getLogger(__name__)


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
        # 114-dim: fac_emb[32] + ts_emb[32] + rm_emb[32] + manual[18].
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

    def _heuristic_score(
        self, day: str, slot: int, is_lab: bool,
        current_load: int, max_load: int = 18,
    ) -> float:
        score = 0.5

        if is_lab:
            if slot in (1, 2):  score += 0.20
            elif slot == 3:     score += 0.12
            elif slot == 4:     score -= 0.05
            elif slot >= 5:     score -= 0.12
        else:
            if slot == 1:       score += 0.15
            elif slot == 2:     score += 0.18
            elif slot == 3:     score += 0.14
            elif slot == 4:     score -= 0.03
            elif slot >= 5:     score -= 0.05

        if day in ("TUE", "WED", "THU"):  score += 0.05
        elif day in ("MON", "FRI"):       score -= 0.02

        ratio = current_load / max(max_load, 1)
        if ratio > 0.9:    score -= 0.30
        elif ratio > 0.7:  score -= 0.10

        return max(0.0, min(1.0, score))
