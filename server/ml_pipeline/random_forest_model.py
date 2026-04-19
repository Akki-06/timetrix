"""
TIMETRIX — Random Forest Slot Suitability Predictor (v2)
=========================================================
File: server/ml_pipeline/random_forest_model.py

Fixes over v1 (AUC 0.76):
  1. Dropped TBD faculty rows from positives — zero embeddings polluted features
  2. Dropped Saturday sessions — SAT removed from scheduler and TimeSlot choices
  3. Fixed Type 1 negatives — no longer generates patterns that ARE in real data
     (same faculty, multi-section, same slot is VALID and was being labeled 0)
  4. Removed room_type_match feature — it was leaking the label directly
  5. Added 3 new negative types with stronger signal:
       Type 5: Faculty teaching outside their available days/slots
       Type 6: Consecutive lab not paired (isolated lab slot)
       Type 7: Load-aware double booking (faculty at weekly cap)
  6. Added 6 new features: weekly load ratio, section count,
     faculty-course affinity score, slot regularity, day diversity,
     is_isolated_lab
  7. GradientBoosting as secondary model — ensembled with RF for better AUC

Run from server/:
    python ml_pipeline/random_forest_model.py

Output (→ ml_pipeline/trained/):
    rf_model.pkl              — trained RF (used by scheduler)
    rf_feature_metadata.pkl   — scaler + feature names + max_hours_map
    rf_training_report.json   — AUC, precision, recall, top features
"""

import json
import pickle
import logging
import random
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

from sklearn.ensemble import (RandomForestClassifier, GradientBoostingClassifier,
                               VotingClassifier)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (roc_auc_score, classification_report,
                             precision_recall_curve,
                             precision_recall_fscore_support)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR  = Path(__file__).resolve().parent.parent
DATA_DIR  = BASE_DIR / "ml_pipeline" / "data"
TRAIN_DIR = BASE_DIR / "ml_pipeline" / "trained"

SESSION_CSV = DATA_DIR / "timetable_dataset.csv"
FACULTY_CSV = DATA_DIR / "faculty_metadata.csv"
ROOMS_CSV   = DATA_DIR / "rooms.csv"
SLOTS_CSV   = DATA_DIR / "timeslots.csv"

EMBED_PATH  = TRAIN_DIR / "node_embeddings.pkl"
RF_MODEL_PATH  = TRAIN_DIR / "rf_model.pkl"
RF_META_PATH   = TRAIN_DIR / "rf_feature_metadata.pkl"
RF_REPORT_PATH = TRAIN_DIR / "rf_training_report.json"

EMBED_DIM   = 32
MANUAL_DIM  = 18    # upgraded from 16: +is_combined, +is_working_day
FEATURE_DIM = EMBED_DIM * 3 + MANUAL_DIM   # 114

ZERO_EMBED = np.zeros(EMBED_DIM, dtype=np.float32)

# Node ID helpers — must match graph_builder.py exactly
def fac_id(n):     return f"FAC::{n.strip()}"
def crs_id(n):     return f"CRS::{n.strip()}"
def rm_id(r):      return f"RRM::{str(r).strip()}"
def ts_id(day, s): return f"TSL::{day[:3].upper()}_S{s}"


# ─────────────────────────────────────────────────────────────────────────────
# PRECOMPUTE STATISTICS FROM REAL DATA
# These are used as features — they encode scheduling patterns
# ─────────────────────────────────────────────────────────────────────────────

def compute_stats(df):
    """
    Precompute per-faculty and per-course statistics from real data.
    These capture pattern knowledge that embeddings alone can't encode.
    """
    named = df[df["faculty"] != "TBD"]

    # Faculty → set of (day, slot) pairs they actually teach
    fac_actual_slots = defaultdict(set)
    for _, row in named.iterrows():
        fac_actual_slots[row["faculty"]].add((row["day"], row["slot_index"]))

    # Faculty → number of unique courses they teach (breadth indicator)
    fac_course_count = named.groupby("faculty")["course_name"].nunique().to_dict()

    # Faculty → number of unique sections they teach
    fac_section_count = named.groupby("faculty")["section"].nunique().to_dict()

    # (faculty, course) → frequency count (affinity)
    fac_course_freq = named.groupby(["faculty", "course_name"]).size().to_dict()

    # Slot → how often it appears in real data (slot popularity)
    slot_popularity = df.groupby("slot_index").size()
    slot_popularity = (slot_popularity / slot_popularity.max()).to_dict()

    # Day → how often it appears (day popularity)
    day_popularity = df.groupby("day").size()
    day_popularity = (day_popularity / day_popularity.max()).to_dict()

    return {
        "fac_actual_slots"  : dict(fac_actual_slots),
        "fac_course_count"  : fac_course_count,
        "fac_section_count" : fac_section_count,
        "fac_course_freq"   : fac_course_freq,
        "slot_popularity"   : slot_popularity,
        "day_popularity"    : day_popularity,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE VECTOR BUILDER — 114 dims
# fac_emb[32] + ts_emb[32] + rm_emb[32] + manual[18]
# ─────────────────────────────────────────────────────────────────────────────

def build_feature_vector(faculty, room, day, slot,
                         is_lab, is_consecutive_lab,
                         contact_hours, semester_int,
                         course_name,
                         embeddings, fac_weekly_load,
                         max_hours_map, stats,
                         fac_today_load=0, max_daily=4,
                         is_combined=0, working_days=None):
    """
    114-dim feature vector for one candidate assignment.

    Layout: [fac_emb(32) | ts_emb(32) | rm_emb(32) | manual(18)]

    The 3 new features (13-15) encode *dynamic scheduling state*:
      13. faculty_load_today_ratio — how full the faculty's day already is.
          At training time this is approximated from row order; at inference
          time the scheduler passes the live tracker value.
      14. slot_adjacent_density — how popular the neighbouring slots (slot±1)
          are in historical data. A slot surrounded by busy neighbours should
          be avoided to spread load.
      15. near_weekly_cap — flag that fires when the faculty is within 15% of
          their weekly limit, acting as a soft "brake" before hard violation.

    Note: room_type_match removed — it leaked the label (v2 fix).
    """
    fac_emb = embeddings.get(fac_id(faculty), ZERO_EMBED) if faculty != "TBD" \
              else ZERO_EMBED
    ts_emb  = embeddings.get(ts_id(day, slot), ZERO_EMBED)
    rm_emb  = embeddings.get(rm_id(room), ZERO_EMBED)

    max_h    = max_hours_map.get(faculty, 18)
    cur_load = fac_weekly_load.get(faculty, 0)

    # Feature 1: load remaining ratio (0=at limit, 1=fully available)
    load_remaining = max(0.0, (max_h - cur_load) / max(max_h, 1))

    # Feature 2: is this a slot the faculty actually teaches in real data?
    actual_slots = stats["fac_actual_slots"].get(faculty, set())
    is_known_slot = 1.0 if (day, slot) in actual_slots else 0.0

    # Feature 3: faculty-course affinity (how often they teach this course)
    freq = stats["fac_course_freq"].get((faculty, course_name), 0)
    # Normalize by max frequency for this faculty
    fac_max_freq = max(
        v for (f, c), v in stats["fac_course_freq"].items()
        if f == faculty
    ) if faculty in stats["fac_course_count"] else 1
    fac_course_affinity = freq / max(fac_max_freq, 1)

    # Feature 4: slot popularity in real data
    slot_pop = stats["slot_popularity"].get(slot, 0.5)

    # Feature 5: day popularity in real data
    day_pop = stats["day_popularity"].get(day, 0.5)

    # Feature 6: is_lab (critical for room assignment)
    # Feature 7: is_consecutive_lab
    # Feature 8: is_morning (slot 1-3)
    is_morning = 1.0 if slot <= 3 else 0.0

    # Feature 9: is_post_lunch (slot 5-6)
    is_post_lunch = 1.0 if slot >= 5 else 0.0

    # Feature 10: semester normalized
    sem_norm = float(semester_int) / 8.0

    # Feature 11: contact hours normalized
    contact_norm = float(contact_hours) / 8.0

    # Feature 12: faculty breadth (how many courses they teach — versatility)
    breadth = stats["fac_course_count"].get(faculty, 1)
    breadth_norm = min(breadth / 10.0, 1.0)

    # ── New features 13-15: dynamic scheduling state ──────────────────────────

    # Feature 13: how loaded is the faculty's day already?
    # 0.0 = empty day, 1.0 = already at daily limit
    fac_today_ratio = float(fac_today_load) / max(float(max_daily), 1.0)

    # Feature 14: popularity of adjacent slots (slot±1).
    # A candidate slot surrounded by already-popular neighbours is likely
    # contributing to bunching — prefer isolated, less-busy neighbourhood.
    adj_left  = stats["slot_popularity"].get(slot - 1, 0.5)
    adj_right = stats["slot_popularity"].get(slot + 1, 0.5)
    slot_adjacent_density = (adj_left + adj_right) / 2.0

    # Feature 15: is the faculty within 15% of their weekly cap?
    # Fires early so the model can softly avoid these assignments before
    # the hard constraint kicks in at exactly max_h.
    near_weekly_cap = 1.0 if cur_load >= max_h * 0.85 else 0.0

    # Feature 16: overload severity — how far above weekly cap
    # 0.0 = at or below cap. Scales linearly above cap.
    overload_severity = max(0.0, (cur_load - max_h) / max(max_h, 1))

    # Feature 17: is_combined (A+B grouping context)
    combined_val = float(is_combined)

    # Feature 18: is_working_day (is this day in section's allowed list?)
    if working_days is None:
        working_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    is_working_day = 1.0 if day in working_days else 0.0

    manual = np.array([
        load_remaining,           # 1:  faculty weekly availability
        is_known_slot,            # 2:  historical slot match
        fac_course_affinity,      # 3:  faculty-course history
        slot_pop,                 # 4:  slot popularity
        day_pop,                  # 5:  day popularity
        float(is_lab),            # 6:  session type
        float(is_consecutive_lab),# 7:  needs consecutive
        is_morning,               # 8:  time of day
        is_post_lunch,            # 9:  post-lunch flag
        sem_norm,                 # 10: semester context
        contact_norm,             # 11: course weight
        breadth_norm,             # 12: faculty versatility
        fac_today_ratio,          # 13: today's load ratio
        slot_adjacent_density,    # 14: busyness of neighbouring slots
        near_weekly_cap,          # 15: approaching weekly limit
        overload_severity,        # 16: how far above weekly cap
        combined_val,             # 17: is_combined
        is_working_day,           # 18: working day match
    ], dtype=np.float32)

    return np.concatenate([fac_emb, ts_emb, rm_emb, manual])  # 114-dim


def get_feature_names():
    names  = [f"fac_emb_{i}" for i in range(EMBED_DIM)]
    names += [f"ts_emb_{i}"  for i in range(EMBED_DIM)]
    names += [f"rm_emb_{i}"  for i in range(EMBED_DIM)]
    names += [
        "load_remaining",           # 1
        "is_known_slot",            # 2
        "fac_course_affinity",      # 3
        "slot_popularity",          # 4
        "day_popularity",           # 5
        "is_lab",                   # 6
        "is_consecutive_lab",       # 7
        "is_morning",               # 8
        "is_post_lunch",            # 9
        "semester_norm",            # 10
        "contact_hours_norm",       # 11
        "faculty_breadth_norm",     # 12
        "fac_today_load_ratio",     # 13
        "slot_adjacent_density",    # 14
        "near_weekly_cap",          # 15
        "overload_severity",        # 16
        "is_combined",              # 17
        "is_working_day",           # 18
    ]
    return names


# ─────────────────────────────────────────────────────────────────────────────
# POSITIVE SAMPLES
# Fix: skip TBD faculty rows and Saturday rows
# ─────────────────────────────────────────────────────────────────────────────

def build_positive_samples(df, embeddings, max_hours_map, stats):
    X, y = [], []
    skipped_tbd = 0
    skipped_sat = 0

    fac_load     = defaultdict(int)                     # weekly load per faculty
    fac_day_load = defaultdict(lambda: defaultdict(int)) # daily load per (faculty, day)

    for _, row in df.iterrows():
        faculty = str(row["faculty"]).strip()
        day     = str(row["day"]).strip()

        # Fix 1: skip TBD — zero embedding creates a spurious "unknown" pattern
        if faculty == "TBD":
            skipped_tbd += 1
            continue

        # Fix 2: skip Saturday — removed from scheduler entirely
        if day == "Saturday":
            skipped_sat += 1
            continue

        # Retrieve how many sessions this faculty already has TODAY in the
        # data we've processed so far — approximates the scheduler state.
        today_load = fac_day_load[faculty][day]
        max_d      = 4   # default max_daily; not stored in training CSVs

        # FIX (Change 1): Cap the weekly load used for positive feature vectors
        # at (max_hours - 1) so positives NEVER appear "overloaded" to the model.
        # Without this cap, late rows for busy faculty accumulate load > max_h,
        # creating positive samples that look overloaded — this confuses Type 3
        # negatives (which are also overloaded) and makes the model ignore
        # load_remaining / overload_severity as discriminative features.
        max_h_pos   = max_hours_map.get(faculty, 18)
        capped_load = min(fac_load[faculty], max(0, max_h_pos - 1))
        capped_fac_weekly_load = dict(fac_load)  # copy
        capped_fac_weekly_load[faculty] = capped_load

        feat = build_feature_vector(
            faculty              = faculty,
            room                 = str(row["room"]).strip(),
            day                  = day,
            slot                 = int(row["slot_index"]),
            is_lab               = int(row["is_lab"]),
            is_consecutive_lab   = int(row["is_consecutive_lab"]),
            contact_hours        = int(row["contact_hours_weekly"]),
            semester_int         = int(row["semester_int"]),
            course_name          = str(row["course_name"]).strip(),
            embeddings           = embeddings,
            fac_weekly_load      = capped_fac_weekly_load,  # capped, not raw
            max_hours_map        = max_hours_map,
            stats                = stats,
            fac_today_load       = today_load,
            max_daily            = max_d,
        )

        if not (np.any(np.isnan(feat)) or np.any(np.isinf(feat))):
            X.append(feat)
            y.append(1)
            fac_load[faculty]         += 1
            fac_day_load[faculty][day] += 1

    log.info(f"  Positives: {len(X)} "
             f"(skipped {skipped_tbd} TBD, {skipped_sat} Saturday)")
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


# ─────────────────────────────────────────────────────────────────────────────
# NEGATIVE SAMPLES — 7 types, all meaningful
# ─────────────────────────────────────────────────────────────────────────────

def build_negative_samples(df, embeddings, max_hours_map, stats,
                            rooms_df, faculty_df, n_negatives):
    X, y = [], []
    rng  = random.Random(SEED)

    # Filter to named faculty, weekday-only rows
    named  = df[(df["faculty"] != "TBD") & (df["day"] != "Saturday")]
    rows   = named.to_dict("records")

    all_days   = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
    all_slots  = [1, 2, 3, 4, 5, 6]
    lab_rooms  = rooms_df[rooms_df["is_lab"] == 1]["room_id"].astype(str).tolist()
    th_rooms   = rooms_df[
        (rooms_df["is_lab"] == 0) &
        (~rooms_df["room_id"].astype(str).isin(["rotation","unknown"]))
    ]["room_id"].astype(str).tolist()
    all_rooms  = lab_rooms + th_rooms

    max_hours  = {r["faculty_name"]: r["max_hours_per_week"]
                  for _, r in faculty_df.iterrows()}

    # Build set of REAL (faculty, day, slot) triples
    # We must NOT generate negatives that appear in real data
    real_triples = {
        (r["faculty"], r["day"], r["slot_index"]) for r in rows
    }

    # Faculty → their known available (day, slot) from real data
    fac_known_slots = stats["fac_actual_slots"]

    # Type 3 (overload) gets 2× share — it's the most critical constraint.
    # The divisor 8 gives the same total budget but lets Type 3 use 2 shares.
    per_type = max(1, n_negatives // 8)

    def add(faculty, room, day, slot, is_lab, consec, hours, sem,
            course, load=0, today_load=0):
        feat = build_feature_vector(
            faculty=faculty, room=room, day=day, slot=slot,
            is_lab=is_lab, is_consecutive_lab=consec,
            contact_hours=hours, semester_int=sem,
            course_name=course,
            embeddings=embeddings,
            fac_weekly_load={faculty: load},
            max_hours_map=max_hours_map,
            stats=stats,
            fac_today_load=today_load,
            max_daily=4,
        )
        if not (np.any(np.isnan(feat)) or np.any(np.isinf(feat))):
            X.append(feat); y.append(0)

    # ── Type 1: REAL double-booking (faculty at same slot, different program)
    # Fix: only use cases where the faculty does NOT appear in real data at
    # that slot — otherwise we're labeling real valid cases as invalid
    log.info("  Type 1: schedule clash (faculty not available at that slot)...")
    count = 0
    for _ in range(per_type * 5):
        if count >= per_type: break
        row   = rng.choice(rows)
        fac   = row["faculty"]
        # Pick a slot the faculty does NOT appear in real data
        actual = fac_known_slots.get(fac, set())
        all_possible = [(d, s) for d in all_days for s in all_slots]
        unknown_slots = [(d,s) for d,s in all_possible if (d,s) not in actual]
        if not unknown_slots: continue
        day, slot = rng.choice(unknown_slots)
        # Don't accidentally recreate a real triple
        if (fac, day, slot) in real_triples: continue
        room = rng.choice(all_rooms)
        add(fac, room, day, slot,
            row["is_lab"], row["is_consecutive_lab"],
            row["contact_hours_weekly"], row["semester_int"],
            row["course_name"], load=0)
        count += 1
    log.info(f"    Generated: {count}")

    # ── Type 2: Wrong room type — lab in theory room or theory in lab room
    log.info("  Type 2: room type mismatch...")
    count = 0
    lab_rows = [r for r in rows if r["is_lab"] == 1]
    th_rows  = [r for r in rows if r["is_lab"] == 0]
    for _ in range(per_type * 4):
        if count >= per_type: break
        if rng.random() < 0.5 and lab_rows and th_rooms:
            row  = rng.choice(lab_rows)
            room = rng.choice(th_rooms)   # lab session in theory room — wrong
        elif th_rows and lab_rooms:
            row  = rng.choice(th_rows)
            room = rng.choice(lab_rooms)  # theory in lab — wrong
        else:
            continue
        add(row["faculty"], room, row["day"], row["slot_index"],
            row["is_lab"], row["is_consecutive_lab"],
            row["contact_hours_weekly"], row["semester_int"],
            row["course_name"])
        count += 1
    log.info(f"    Generated: {count}")

    # ── Type 3: Faculty overload — EXACT CLONE of real positive rows
    # FIX (Change 2+3): The OLD approach picked random rows with random high loads.
    # The GNN embeddings for those random combos differed from real positives, so
    # the model learned to distinguish valid vs invalid by *embedding match*, not
    # by load features. Result: the sanity check for overloaded faculty scored 0.998
    # instead of < 0.4 — the model was completely ignoring load_remaining.
    #
    # NEW approach: clone REAL positive rows (same faculty, room, day, slot, course)
    # but inject load = max_h + high. Now both the positive and negative share the
    # SAME embeddings — the model MUST use load_remaining / overload_severity to
    # distinguish them. This is a «contrastive pair» strategy.
    #
    # Type 3 budget is doubled (2 * per_type) because overload is the most critical
    # constraint to enforce — it must dominate the negative distribution.
    log.info("  Type 3: faculty overload (contrastive pairs from real positives)...")
    count = 0
    for _ in range(per_type * 6):  # attempt 6x to fill 2x budget
        if count >= per_type * 2: break
        row   = rng.choice(rows)
        fac   = row["faculty"]
        max_h = max_hours.get(fac, 18)
        # Inject clearly-over-cap load (4–12 hours above weekly limit)
        load  = max_h + rng.randint(4, 12)
        # Simulate the day already being packed (over daily limit)
        today = rng.randint(5, 9)
        # Use EXACT same room/day/slot/course as the real row — only load differs.
        # This creates a minimal contrastive pair: everything identical except load.
        add(fac, row["room"], row["day"], row["slot_index"],
            row["is_lab"], row["is_consecutive_lab"],
            row["contact_hours_weekly"], row["semester_int"],
            row["course_name"], load=load, today_load=today)
        count += 1
    log.info(f"    Generated: {count}")

    # ── Type 4: Lab not paired (isolated slot, not consecutive)
    # A lab session in a single isolated slot — missing its pair
    log.info("  Type 4: unpaired lab slot...")
    count = 0
    for _ in range(per_type * 4):
        if count >= per_type: break
        if not lab_rows: break
        row  = rng.choice(lab_rows)
        # Put it in a slot that CANNOT be consecutive (slot 6 has no pair)
        isolated_slot = 6
        room = rng.choice(lab_rooms) if lab_rooms else row["room"]
        add(row["faculty"], room, row["day"], isolated_slot,
            is_lab=1, consec=0,   # lab=1 but consecutive=0 — invalid
            hours=row["contact_hours_weekly"],
            sem=row["semester_int"],
            course=row["course_name"])
        count += 1
    log.info(f"    Generated: {count}")

    # ── Type 5: Visiting faculty on random days (they have restricted schedule)
    log.info("  Type 5: visiting faculty scheduling violation...")
    visiting = faculty_df[faculty_df["employment_type"] == "Visiting"][
        "faculty_name"].tolist()
    fac_groups = defaultdict(list)
    for r in rows:
        fac_groups[r["faculty"]].append(r)

    count = 0
    for _ in range(per_type * 5):
        if count >= per_type: break
        if not visiting: break
        fac  = rng.choice(visiting)
        fac_rows = fac_groups.get(fac, [])
        if not fac_rows: continue
        row  = rng.choice(fac_rows)
        # Put visiting faculty in a slot completely outside their known slots
        actual = fac_known_slots.get(fac, set())
        bad_options = [(d,s) for d in all_days for s in all_slots
                       if (d,s) not in actual and (fac,d,s) not in real_triples]
        if not bad_options: continue
        day, slot = rng.choice(bad_options)
        add(fac, row["room"], day, slot,
            row["is_lab"], row["is_consecutive_lab"],
            row["contact_hours_weekly"], row["semester_int"],
            row["course_name"])
        count += 1
    log.info(f"    Generated: {count}")

    # ── Type 6: Random wrong faculty for a course they've never taught
    log.info("  Type 6: faculty-course mismatch...")
    # Build set of (faculty, course) pairs that appear in real data
    real_fac_course = {(r["faculty"], r["course_name"]) for r in rows}
    all_faculty = list({r["faculty"] for r in rows})
    count = 0
    for _ in range(per_type * 4):
        if count >= per_type: break
        row  = rng.choice(rows)
        # Pick a faculty who has NEVER taught this course
        fac  = rng.choice(all_faculty)
        if (fac, row["course_name"]) in real_fac_course: continue
        if (fac, row["day"], row["slot_index"]) in real_triples: continue
        add(fac, row["room"], row["day"], row["slot_index"],
            row["is_lab"], row["is_consecutive_lab"],
            row["contact_hours_weekly"], row["semester_int"],
            row["course_name"])
        count += 1
    log.info(f"    Generated: {count}")

    # ── Type 7: Late-day lab (labs should be morning — slot 5/6 is poor)
    log.info("  Type 7: late-day lab scheduling...")
    count = 0
    for _ in range(per_type * 4):
        if count >= per_type: break
        if not lab_rows or not lab_rooms: break
        row  = rng.choice(lab_rows)
        room = rng.choice(lab_rooms)
        # Force to post-lunch isolated slot
        bad_slot = rng.choice([5, 6])
        add(row["faculty"], room, row["day"], bad_slot,
            is_lab=1, consec=0,
            hours=row["contact_hours_weekly"],
            sem=row["semester_int"],
            course=row["course_name"])
        count += 1
    log.info(f"    Generated: {count}")

    # ── Type 8: lab course assigned to theory room (room-type violation)
    # Hard-mined: the scheduler should NEVER put a lab course in a THEORY room.
    log.info("  Type 8: lab course placed in theory room...")
    theory_rooms = [
        str(r["room_id"]) for _, r in rooms_df.iterrows()
        if str(r.get("room_type", "")).upper() == "THEORY"
    ]
    count = 0
    for _ in range(per_type * 4):
        if count >= per_type: break
        if not lab_rows or not theory_rooms: break
        row  = rng.choice(lab_rows)
        room = rng.choice(theory_rooms)
        add(row["faculty"], room, row["day"], row["slot_index"],
            is_lab=1, consec=row.get("is_consecutive_lab", 1),
            hours=row["contact_hours_weekly"],
            sem=row["semester_int"],
            course=row["course_name"])
        count += 1
    log.info(f"    Generated: {count}")

    # ── Type 9: cross-semester mismatch (faculty teaching a course in a
    # semester they've never taught — simulates assignment error).
    log.info("  Type 9: cross-semester faculty mismatch...")
    all_sem_set = sorted(df["semester_int"].dropna().unique().tolist())
    fac_sem_freq = defaultdict(set)
    for _, r in df.iterrows():
        fac_sem_freq[r["faculty"]].add(r["semester_int"])
    count = 0
    for _ in range(per_type * 4):
        if count >= per_type: break
        if not all_sem_set: break
        row = rng.choice(df.to_dict("records"))
        unknown_sems = [s for s in all_sem_set if s not in fac_sem_freq.get(row["faculty"], set())]
        if not unknown_sems:
            continue
        bad_sem = rng.choice(unknown_sems)
        add(row["faculty"], row["room"], row["day"], row["slot_index"],
            is_lab=row.get("is_lab", 0), consec=row.get("is_consecutive_lab", 0),
            hours=row["contact_hours_weekly"],
            sem=bad_sem,
            course=row["course_name"])
        count += 1
    log.info(f"    Generated: {count}")

    # ── Type 10: high-load day clustering — same faculty getting packed into
    # ≥4 sessions on the same day (simulates the scheduler ignoring daily caps).
    log.info("  Type 10: faculty over-packed on a single day...")
    count = 0
    fac_day_freq = defaultdict(int)
    for _, r in df.iterrows():
        fac_day_freq[(r["faculty"], r["day"])] += 1
    over_packed_examples = [
        (fac, day) for (fac, day), n in fac_day_freq.items() if n >= 4
    ]
    # If no natural examples, synthesize: pick random faculty+day and flood.
    for _ in range(per_type * 4):
        if count >= per_type: break
        row = rng.choice(df.to_dict("records"))
        # 5th/6th slot stacked onto an already-busy day = violation
        add(row["faculty"], row["room"], row["day"], rng.choice([5, 6]),
            is_lab=0, consec=0,
            hours=row["contact_hours_weekly"],
            sem=row["semester_int"],
            course=row["course_name"])
        count += 1
    log.info(f"    Generated: {count}")

    log.info(f"  Total negatives: {len(X)}")
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


# ─────────────────────────────────────────────────────────────────────────────
# TRAINING
# ─────────────────────────────────────────────────────────────────────────────

def train(X, y):
    """
    Train an ensemble model and return (final_model, scaler, cv_results,
    oob_score, optimal_threshold).

    Pipeline:
    1. Fit plain RF to get OOB score and cross-val metrics (cheap baseline).
    2. Wrap RF in CalibratedClassifierCV(isotonic) — fixes the known problem
       that RandomForest probabilities cluster near 0/1 and are poorly
       calibrated. Isotonic regression maps them to true probabilities.
    3. Fit GradientBoosting as a second estimator (different bias/variance
       trade-off from RF, naturally better calibrated).
    4. Combine into a soft-voting VotingClassifier — averages predict_proba()
       from both estimators. No extra CV needed, fast, single predict_proba()
       interface used by the scheduler unchanged.
    5. Threshold tuning — find the probability cutoff that maximises F1 on
       training data (slightly optimistic but gives a good starting point).
       Scheduler uses this to split candidates into "preferred" vs "fallback".
    """

    log.info(f"  Samples: {len(y)} | Pos: {y.sum()} | Neg: {(y==0).sum()}")
    log.info(f"  Feature dims: {X.shape[1]}")

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── Step 1: plain RF for baseline metrics ─────────────────────────────────
    # FIX (Change 4): Regularized RF — shallower trees and larger leaf requirements
    # prevent memorization of noise while preserving the strong signal.
    # max_depth 20→14: stops the tree from growing arbitrary long decision paths.
    # min_samples_leaf 1→4: each leaf must represent at least 4 real examples.
    # min_samples_split 2→8: a node must have ≥8 samples before it can split.
    rf_base = RandomForestClassifier(
        n_estimators     = 400,
        max_depth        = 14,          # was 20 — reduced to prevent memorization
        min_samples_leaf = 4,           # was 1 — needs ≥4 samples at each leaf
        min_samples_split= 8,           # was 2 — needs ≥8 samples to attempt split
        max_features     = "sqrt",
        class_weight     = "balanced",
        random_state     = SEED,
        n_jobs           = -1,
        oob_score        = True,
    )

    log.info("  Running 5-fold CV on base RF...")
    cv  = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    cvr = cross_validate(
        rf_base, X_scaled, y, cv=cv,
        scoring=["accuracy", "f1", "roc_auc"],
        return_train_score=False,
    )

    log.info(f"  CV Accuracy : {cvr['test_accuracy'].mean():.4f} "
             f"± {cvr['test_accuracy'].std():.4f}")
    log.info(f"  CV F1       : {cvr['test_f1'].mean():.4f} "
             f"± {cvr['test_f1'].std():.4f}")
    log.info(f"  CV ROC-AUC  : {cvr['test_roc_auc'].mean():.4f} "
             f"± {cvr['test_roc_auc'].std():.4f}")

    # Fit RF on full data to get OOB score
    rf_base.fit(X_scaled, y)
    log.info(f"  OOB score: {rf_base.oob_score_:.4f}")
    oob_score = rf_base.oob_score_

    # ── Step 2: calibrate RF ───────────────────────────────────────────────────
    # CalibratedClassifierCV with cv=3 refits the estimator 3 times using
    # out-of-fold predictions to fit an isotonic regression calibrator.
    # Result: predict_proba() values are actual probabilities, not raw scores.
    log.info("  Calibrating RF with isotonic regression (cv=3)...")
    rf_calibrated = CalibratedClassifierCV(
        estimator = rf_base,
        method    = "isotonic",
        cv        = 3,
    )
    rf_calibrated.fit(X_scaled, y)
    log.info("  RF calibration done.")

    # ── Step 3: GradientBoosting ───────────────────────────────────────────────
    # GB has a different bias/variance profile from RF and is naturally better
    # calibrated, making it a complementary estimator for the ensemble.
    # FIX (Change 5): Regularized GB — fewer estimators, shallower trees, min_leaf.
    log.info("  Training GradientBoosting (n=150, depth=4)...")
    gb = GradientBoostingClassifier(
        n_estimators     = 150,         # was 200 — fewer trees, less overfitting
        max_depth        = 4,           # was 5 — shallower
        learning_rate    = 0.05,
        subsample        = 0.8,
        min_samples_leaf = 4,           # new — leaf regularization
        random_state     = SEED,
    )
    gb.fit(X_scaled, y)
    log.info("  GradientBoosting done.")

    # ── Step 4: soft-voting ensemble ──────────────────────────────────────────
    # VotingClassifier(voting='soft') averages predict_proba() from both
    # estimators. The combined model has the same interface as a plain RF:
    # model.predict_proba(X_scaled)[0][1] — no changes needed in the scheduler.
    log.info("  Building soft-voting ensemble (RF_calibrated + GB)...")
    final_model = VotingClassifier(
        estimators = [("rf", rf_calibrated), ("gb", gb)],
        voting     = "soft",
        n_jobs     = -1,
    )
    final_model.fit(X_scaled, y)
    log.info("  Ensemble done.")

    # ── Step 5: held-out threshold tuning (improvement #9) ───────────────────
    # Threshold tuning on the training set is optimistic. Instead, hold out
    # ~20% of the data, fit on 80%, and tune F1 on the val slice.
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_scaled, y, test_size=0.20, stratify=y, random_state=SEED,
    )
    log.info(f"  Threshold tuning on held-out set: "
             f"train={len(y_tr)} val={len(y_val)} "
             f"(val_pos={int(y_val.sum())})")

    # Mirror the regularized RF/GB configs in the val model for fair threshold.
    val_model = VotingClassifier(
        estimators = [
            ("rf", CalibratedClassifierCV(
                estimator=RandomForestClassifier(
                    n_estimators=400, max_depth=14,
                    min_samples_leaf=4, min_samples_split=8,
                    max_features="sqrt", class_weight="balanced",
                    random_state=SEED, n_jobs=-1,
                ),
                method="isotonic", cv=3,
            )),
            ("gb", GradientBoostingClassifier(
                n_estimators=150, max_depth=4, learning_rate=0.05,
                subsample=0.8, min_samples_leaf=4, random_state=SEED,
            )),
        ],
        voting="soft", n_jobs=-1,
    )
    val_model.fit(X_tr, y_tr)
    y_val_scores = val_model.predict_proba(X_val)[:, 1]
    val_auc = float(roc_auc_score(y_val, y_val_scores))
    log.info(f"  Held-out val AUC: {val_auc:.4f}")

    precisions, recalls, thresholds = precision_recall_curve(y_val, y_val_scores)
    denom = precisions[:-1] + recalls[:-1]
    denom = np.where(denom > 0, denom, 1.0)
    f1_scores = 2 * precisions[:-1] * recalls[:-1] / denom
    best_idx   = int(np.argmax(f1_scores))
    optimal_threshold = float(thresholds[best_idx])
    optimal_threshold = max(0.30, min(0.70, optimal_threshold))
    log.info(f"  Optimal threshold (val set): {optimal_threshold:.4f} "
             f"(F1={f1_scores[best_idx]:.4f})")

    # FIX (Change 6): Per-class precision/recall report on held-out val set.
    # This gives a clearer picture than AUC alone — especially for the minority
    # class (valid slots) where high overall AUC can hide poor recall.
    from sklearn.metrics import classification_report
    y_val_pred = (y_val_scores >= optimal_threshold).astype(int)
    report_str = classification_report(
        y_val, y_val_pred,
        target_names=["invalid_slot", "valid_slot"],
        digits=4,
    )
    log.info(f"  Per-class classification report (threshold={optimal_threshold:.4f}):\n{report_str}")

    # Attach val_auc to cvr-like dict for the report.
    cvr = dict(cvr)
    cvr["val_auc"] = np.array([val_auc])

    return final_model, scaler, cvr, oob_score, optimal_threshold


# ─────────────────────────────────────────────────────────────────────────────
# SANITY CHECK
# ─────────────────────────────────────────────────────────────────────────────

def sanity_check(rf, scaler, embeddings, max_hours_map, stats):
    """
    Score known valid vs known invalid assignments.
    Uses real faculty from training data.
    """
    def score(faculty, room, day, slot, is_lab, consec, hours, sem, course, load=0):
        feat = build_feature_vector(
            faculty=faculty, room=room, day=day, slot=slot,
            is_lab=is_lab, is_consecutive_lab=consec,
            contact_hours=hours, semester_int=sem, course_name=course,
            embeddings=embeddings,
            fac_weekly_load={faculty: load},
            max_hours_map=max_hours_map,
            stats=stats,
        )
        f = scaler.transform(feat.reshape(1, -1))
        return float(rf.predict_proba(f)[0][1])

    # Valid: Rahul Bhatt teaches DBMS Monday S2 in theory room (real pattern)
    s1 = score("Mr. Rahul Bhatt", "1118", "Monday", 2,
                is_lab=0, consec=0, hours=4, sem=4,
                course="Database Management Systems", load=2)

    # Invalid: Rahul Bhatt in a lab room for theory course
    s2 = score("Mr. Rahul Bhatt", "1108", "Monday", 2,
                is_lab=0, consec=0, hours=4, sem=4,
                course="Database Management Systems", load=2)

    # Invalid: massively overloaded
    s3 = score("Mr. Rahul Bhatt", "1118", "Monday", 2,
                is_lab=0, consec=0, hours=4, sem=4,
                course="Database Management Systems", load=25)

    # Invalid: faculty never taught this course
    s4 = score("Ms. Manvi Chopra", "1118", "Monday", 2,
                is_lab=0, consec=0, hours=4, sem=4,
                course="Database Management Systems", load=0)

    log.info("Sanity check:")
    log.info(f"  Valid (real pattern)      : {s1:.4f}  (want > 0.5)")
    log.info(f"  Wrong room type           : {s2:.4f}  (want < valid)")
    log.info(f"  Overloaded faculty        : {s3:.4f}  (want < 0.4)")
    log.info(f"  Faculty never taught course: {s4:.4f}  (want < valid)")

    return {"valid": s1, "wrong_room": s2, "overloaded": s3, "wrong_faculty": s4}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    TRAIN_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Loading data...")
    df         = pd.read_csv(SESSION_CSV)
    faculty_df = pd.read_csv(FACULTY_CSV)
    rooms_df   = pd.read_csv(ROOMS_CSV)
    df["course_code"] = df["course_code"].fillna("")
    rooms_df["lab_type"] = rooms_df["lab_type"].fillna("")

    with open(EMBED_PATH, "rb") as f:
        embeddings = pickle.load(f)

    log.info(f"  Sessions: {len(df)} | Embeddings: {len(embeddings)}")

    max_hours_map = {
        r["faculty_name"]: r["max_hours_per_week"]
        for _, r in faculty_df.iterrows()
    }

    # Precompute pattern statistics
    log.info("Computing statistics from real data...")
    stats = compute_stats(df)
    log.info(f"  Faculty with known slots: {len(stats['fac_actual_slots'])}")
    log.info(f"  Faculty-course pairs: {len(stats['fac_course_freq'])}")

    # Positives
    log.info("Building positive samples...")
    X_pos, y_pos = build_positive_samples(df, embeddings, max_hours_map, stats)

    # Negatives
    log.info("Building negative samples (10 types)...")
    n_neg = len(y_pos) * 3   # 3× negatives
    X_neg, y_neg = build_negative_samples(
        df, embeddings, max_hours_map, stats,
        rooms_df, faculty_df, n_neg
    )

    # Combine + shuffle
    X = np.vstack([X_pos, X_neg])
    y = np.concatenate([y_pos, y_neg])
    idx = np.random.permutation(len(y))
    X, y = X[idx], y[idx]
    log.info(f"Total: {len(y)} | Pos: {y.sum()} | Neg: {(y==0).sum()}")

    # Train
    log.info("Training ensemble model (RF_calibrated + GradientBoosting)...")
    final_model, scaler, cvr, oob_score, optimal_threshold = train(X, y)

    # Feature importance — pull from the RF inside the VotingClassifier.
    # VotingClassifier stores estimators as .estimators_[i].
    # estimators_[0] is the CalibratedClassifierCV; its base_estimator is
    # the fitted RF from the last CV fold (calibrators_[*].calibrated_classifiers).
    # Safest: try to extract, fall back gracefully.
    names = get_feature_names()
    try:
        # Access the RF base inside CalibratedClassifierCV
        rf_inside = final_model.estimators_[0]   # CalibratedClassifierCV
        # calibrated_classifiers is a list of (estimator, calibrator) pairs
        inner_rf = rf_inside.calibrated_classifiers_[0].estimator
        imp  = inner_rf.feature_importances_
        top  = sorted(enumerate(imp), key=lambda x: -x[1])[:15]
        log.info("Top 15 features (from RF inside ensemble):")
        for fidx, importance in top:
            fname = names[fidx] if fidx < len(names) else f"feat_{fidx}"
            bar   = "█" * int(importance * 300)
            log.info(f"  {fname:<30s} {bar} {importance:.4f}")
    except Exception as e:
        log.warning(f"  Could not extract feature importances: {e}")
        imp = np.zeros(FEATURE_DIM)
        top = []

    # Sanity check — still uses the ensemble's predict_proba transparently
    sanity = sanity_check(final_model, scaler, embeddings, max_hours_map, stats)

    # Save
    log.info("Saving...")

    with open(RF_MODEL_PATH, "wb") as f:
        pickle.dump(final_model, f, protocol=pickle.HIGHEST_PROTOCOL)

    with open(RF_META_PATH, "wb") as f:
        pickle.dump({
            "scaler"             : scaler,
            "feature_names"      : names,
            "feature_dim"        : FEATURE_DIM,
            "embed_dim"          : EMBED_DIM,
            "max_hours_map"      : max_hours_map,
            "stats"              : stats,           # needed by scheduler
            "optimal_threshold"  : optimal_threshold,  # for candidate filtering
        }, f, protocol=pickle.HIGHEST_PROTOCOL)

    val_auc = float(cvr.get("val_auc", [0.0])[0]) if "val_auc" in cvr else None
    report = {
        "cv_accuracy"       : round(float(cvr["test_accuracy"].mean()), 4),
        "cv_f1"             : round(float(cvr["test_f1"].mean()), 4),
        "cv_roc_auc"        : round(float(cvr["test_roc_auc"].mean()), 4),
        "val_auc"           : round(val_auc, 4) if val_auc is not None else None,
        "oob_score"         : round(float(oob_score), 4),
        "optimal_threshold" : round(optimal_threshold, 4),
        "n_positives"       : int(y.sum()),
        "n_negatives"       : int((y == 0).sum()),
        "negative_types"    : 10,
        "feature_dim"       : FEATURE_DIM,
        "sanity_check"      : sanity,
        "top_features"      : [
            {"feature"   : names[i] if i < len(names) else f"feat_{i}",
             "importance": round(float(imp[i]), 6)}
            for i, _ in top
        ],
    }

    with open(RF_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    log.info(f"  Model     → {RF_MODEL_PATH}")
    log.info(f"  Meta      → {RF_META_PATH}")
    log.info(f"  Report    → {RF_REPORT_PATH}")
    log.info(f"Done. CV AUC={report['cv_roc_auc']:.4f}, "
             f"OOB={report['oob_score']:.4f}, "
             f"threshold={optimal_threshold:.4f}")

    return final_model, scaler


if __name__ == "__main__":
    main()
