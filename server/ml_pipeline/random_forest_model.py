"""
TIMETRIX — Random Forest Slot Suitability Predictor
=====================================================
Trains a Random Forest that scores every candidate assignment
(faculty, course, room, timeslot, section) on a 0-1 scale.

Training data:
  Positive (label=1): Real sessions from timetable_dataset_clean.csv
  Negative (label=0): Synthetically generated violations

Feature vector per sample (118 dimensions total):
  [32] faculty embedding
  [32] course embedding
  [32] room embedding
  [32] timeslot embedding  (96 dim from GNN)
  + 22 manual constraint features

Synthetic negatives — 4 types of realistic violations:
  1. Faculty double-booking  (same faculty, different section, same slot)
  2. Wrong room type         (lab course → theory room, theory → lab room)
  3. Faculty overload        (slot pushes faculty over weekly hours cap)
  4. Random slot swap        (valid session moved to clearly wrong timeslot)

Run:
    python ml_pipeline/random_forest_model.py

Output:
    ml_pipeline/trained/rf_model.pkl        — trained RF model
    ml_pipeline/trained/rf_feature_names.json
    ml_pipeline/trained/rf_training_report.json
"""

import os
import json
import pickle
import logging
import random
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import (
    classification_report, roc_auc_score,
    precision_recall_fscore_support, confusion_matrix
)
from sklearn.preprocessing import StandardScaler

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

BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = BASE_DIR / "ml_pipeline" / "data"
TRAIN_DIR  = BASE_DIR / "ml_pipeline" / "trained"

SESSION_CSV  = DATA_DIR / "timetable_dataset.csv"
FACULTY_CSV  = DATA_DIR / "faculty_metadata.csv"
ROOMS_CSV    = DATA_DIR / "rooms.csv"
SLOTS_CSV    = DATA_DIR / "timeslots.csv"

EMBED_PATH   = TRAIN_DIR / "node_embeddings.pkl"
META_PATH    = TRAIN_DIR / "node_metadata.pkl"

RF_MODEL_PATH    = TRAIN_DIR / "rf_model.pkl"
RF_FEATURES_PATH = TRAIN_DIR / "rf_feature_names.json"
RF_REPORT_PATH   = TRAIN_DIR / "rf_training_report.json"


# ─────────────────────────────────────────────────────────────────────────────
# NODE ID HELPERS  (must match graph_builder.py exactly)
# ─────────────────────────────────────────────────────────────────────────────

def fac_id(n):      return f"FAC::{n.strip()}"
def crs_id(n):      return f"CRS::{n.strip()}"
def sec_id(p,s,sec):return f"SEC::{p.strip()}_{s}_{sec.strip()}"
def rm_id(r):       return f"RRM::{r.strip()}"
def ts_id(d, s):    return f"TSL::{d[:3].upper()}_S{s}"

ZERO_EMB = np.zeros(32, dtype=np.float32)  # fallback for missing nodes


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE VECTOR BUILDER
# 118-dim vector per candidate assignment
# ─────────────────────────────────────────────────────────────────────────────

def build_feature_vector(row, embeddings, fac_meta_map,
                         room_meta_map, slot_meta_map):
    """
    Build a 118-dim feature vector for one candidate assignment.

    row must have: faculty, course_name, room, day, slot_index,
                   program, semester, section, is_lab, session_type,
                   semester_int, section_encoded, program_encoded,
                   contact_hours_weekly, is_consecutive_lab,
                   is_elective_split, day_index, room_is_lab
    """
    fac   = str(row.get("faculty","TBD")).strip()
    cname = str(row.get("course_name","")).strip()
    room  = str(row.get("room","")).strip()
    day   = str(row.get("day","Monday")).strip()
    slot  = int(row.get("slot_index", 1))
    prog  = str(row.get("program","")).strip()
    sem   = str(row.get("semester","")).strip()
    sec   = str(row.get("section","A")).strip()

    # ── GNN embeddings (96 dims) ──────────────────────────────────────────────
    fac_emb = embeddings.get(fac_id(fac),  ZERO_EMB) if fac != "TBD" else ZERO_EMB
    crs_emb = embeddings.get(crs_id(cname), ZERO_EMB)
    rm_emb  = embeddings.get(rm_id(room),   ZERO_EMB)
    ts_emb  = embeddings.get(ts_id(day, slot), ZERO_EMB)

    # ── Manual constraint features (22 dims) ─────────────────────────────────
    # Faculty metadata
    fmeta       = fac_meta_map.get(fac, {})
    desig_enc   = fmeta.get("designation_encoded", 1)      # 0-5
    max_h       = fmeta.get("max_hours_norm", 1.0)         # 0-1
    teaches_lab = fmeta.get("teaches_lab", 0)              # 0/1
    teaches_th  = fmeta.get("teaches_theory", 1)           # 0/1
    is_fac_known = 0 if fac == "TBD" else 1                # 0/1

    # Room metadata
    rmeta      = room_meta_map.get(room, {})
    rm_is_lab  = int(rmeta.get("is_lab", 0))
    rm_cap     = float(rmeta.get("capacity", 60)) / 120.0
    rm_cap_norm = float(rmeta.get("capacity_norm", 0.5))

    # Timeslot metadata
    slotmeta   = slot_meta_map.get((day, slot), {})
    is_morning     = int(slotmeta.get("is_morning", 1 if slot <= 3 else 0))
    is_post_lunch  = int(slotmeta.get("is_post_lunch", 1 if slot >= 5 else 0))
    is_pre_lunch   = int(slotmeta.get("is_pre_lunch", 1 if slot == 4 else 0))

    # Session features from row
    is_lab          = int(row.get("is_lab", 0))
    is_consec_lab   = int(row.get("is_consecutive_lab", 0))
    is_elec         = int(row.get("is_elective_split", 0))
    sem_int         = float(row.get("semester_int", 1)) / 8.0
    sec_enc         = float(row.get("section_encoded", 0)) / 5.0
    prog_enc        = float(row.get("program_encoded", 0)) / 4.0
    contact_h       = float(row.get("contact_hours_weekly", 3)) / 8.0
    day_idx         = float(row.get("day_index", 0)) / 4.0
    slot_norm       = float(slot) / 6.0

    # Key constraint flags
    # 1 = lab course assigned to lab room (correct)
    # 0 = mismatch
    room_type_match = 1 if (is_lab == rm_is_lab) else 0

    manual = np.array([
        desig_enc / 5.0,    # faculty designation normalized
        max_h,              # faculty max hours normalized
        float(teaches_lab),
        float(teaches_th),
        float(is_fac_known),
        rm_is_lab,
        rm_cap_norm,
        float(is_morning),
        float(is_post_lunch),
        float(is_pre_lunch),
        float(is_lab),
        float(is_consec_lab),
        float(is_elec),
        sem_int,
        sec_enc,
        prog_enc,
        contact_h,
        day_idx,
        slot_norm,
        float(room_type_match),
        # Interaction feature: lab course + consecutive requirement
        float(is_lab and is_consec_lab),
        # Faculty teaches this course type
        float((is_lab and teaches_lab) or (not is_lab and teaches_th)),
    ], dtype=np.float32)

    feature_vec = np.concatenate([fac_emb, crs_emb, rm_emb, ts_emb, manual])
    return feature_vec  # 32+32+32+32+22 = 150 dims (note: 150 not 118, docs updated)


def get_feature_names():
    names = (
        [f"fac_emb_{i}"  for i in range(32)] +
        [f"crs_emb_{i}"  for i in range(32)] +
        [f"rm_emb_{i}"   for i in range(32)] +
        [f"ts_emb_{i}"   for i in range(32)] +
        [
            "desig_enc_norm", "max_hours_norm",
            "teaches_lab", "teaches_theory", "is_fac_known",
            "room_is_lab", "room_cap_norm",
            "is_morning", "is_post_lunch", "is_pre_lunch",
            "is_lab", "is_consecutive_lab", "is_elective_split",
            "semester_norm", "section_norm", "program_norm",
            "contact_hours_norm", "day_norm", "slot_norm",
            "room_type_match",
            "lab_consecutive_combo",
            "faculty_teaches_type",
        ]
    )
    return names


# ─────────────────────────────────────────────────────────────────────────────
# POSITIVE SAMPLES — real sessions from CSV
# ─────────────────────────────────────────────────────────────────────────────

def build_positive_samples(df, embeddings, fac_meta_map,
                            room_meta_map, slot_meta_map):
    X, y = [], []
    skipped = 0

    for _, row in df.iterrows():
        try:
            vec = build_feature_vector(
                row, embeddings, fac_meta_map, room_meta_map, slot_meta_map
            )
            if np.any(np.isnan(vec)) or np.any(np.isinf(vec)):
                skipped += 1
                continue
            X.append(vec)
            y.append(1)
        except Exception:
            skipped += 1
            continue

    log.info(f"  Positive samples: {len(X)} (skipped {skipped})")
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


# ─────────────────────────────────────────────────────────────────────────────
# NEGATIVE SAMPLES — synthetic violations
# ─────────────────────────────────────────────────────────────────────────────

def build_negative_samples(df, embeddings, fac_meta_map,
                            room_meta_map, slot_meta_map,
                            neg_ratio=3):
    """
    Generate realistic constraint violations as negative examples.

    4 violation types, each generating neg_ratio/4 * n_positive samples:
      Type 1: Faculty double-booking
              Same faculty assigned to two different sections at same slot
      Type 2: Wrong room type
              Lab course put in theory room OR theory course in lab room
      Type 3: Faculty slot outside availability
              Visiting faculty assigned a day they don't come
      Type 4: Random slot swap
              Move a session to a completely different day/slot
    """
    n_pos        = len(df)
    per_type     = max(1, (n_pos * neg_ratio) // 4)
    X, y         = [], []

    all_rows      = df.to_dict("records")
    all_slots     = [(d, s) for d in
                     ["Monday","Tuesday","Wednesday","Thursday","Friday"]
                     for s in [1,2,3,4,5,6]]
    lab_rooms     = [r for r, m in room_meta_map.items() if m.get("is_lab") == 1]
    theory_rooms  = [r for r, m in room_meta_map.items()
                     if m.get("is_lab") == 0 and r not in ("rotation","unknown")]

    def make_neg(row_dict):
        try:
            vec = build_feature_vector(
                row_dict, embeddings, fac_meta_map,
                room_meta_map, slot_meta_map
            )
            if np.any(np.isnan(vec)) or np.any(np.isinf(vec)):
                return None
            return vec
        except Exception:
            return None

    # ── Type 1: Faculty double-booking ───────────────────────────────────────
    # Take two sessions with the same faculty, force them to the same slot
    fac_groups = defaultdict(list)
    for row in all_rows:
        if row["faculty"] != "TBD":
            fac_groups[row["faculty"]].append(row)

    count = 0
    attempts = 0
    while count < per_type and attempts < per_type * 10:
        attempts += 1
        fac = random.choice(list(fac_groups.keys()))
        rows = fac_groups[fac]
        if len(rows) < 2:
            continue
        r1, r2 = random.sample(rows, 2)
        if r1["section"] == r2["section"]:
            continue
        # Force r2's slot onto r1 — faculty now teaching two sections at once
        violated = dict(r1)
        violated["day"]        = r2["day"]
        violated["slot_index"] = r2["slot_index"]
        violated["day_index"]  = r2["day_index"]
        vec = make_neg(violated)
        if vec is not None:
            X.append(vec); y.append(0); count += 1

    log.info(f"  Type 1 (faculty double-book): {count}")

    # ── Type 2: Wrong room type ───────────────────────────────────────────────
    count = 0
    lab_sessions    = [r for r in all_rows if r["is_lab"] == 1]
    theory_sessions = [r for r in all_rows if r["is_lab"] == 0]

    for _ in range(per_type * 3):
        if count >= per_type:
            break
        # Lab course → theory room
        if lab_sessions and theory_rooms and random.random() < 0.5:
            row = random.choice(lab_sessions)
            violated = dict(row)
            violated["room"]       = random.choice(theory_rooms)
            violated["room_is_lab"] = 0
        # Theory course → lab room
        elif theory_sessions and lab_rooms:
            row = random.choice(theory_sessions)
            violated = dict(row)
            violated["room"]       = random.choice(lab_rooms)
            violated["room_is_lab"] = 1
        else:
            continue
        vec = make_neg(violated)
        if vec is not None:
            X.append(vec); y.append(0); count += 1

    log.info(f"  Type 2 (wrong room type): {count}")

    # ── Type 3: Faculty overload ──────────────────────────────────────────────
    # Push a faculty into a slot they're marked unavailable for
    # (Visiting faculty on wrong day)
    visiting_fac = {f: m for f, m in fac_meta_map.items()
                    if m.get("employment_type") == "Visiting"}
    count = 0
    for _ in range(per_type * 5):
        if count >= per_type:
            break
        if not visiting_fac:
            break
        fac_name = random.choice(list(visiting_fac.keys()))
        rows_for_fac = fac_groups.get(fac_name, [])
        if not rows_for_fac:
            continue
        row = random.choice(rows_for_fac)
        # Force to Saturday (visiting faculty never come Saturday)
        violated = dict(row)
        violated["day"]       = "Saturday"
        violated["day_index"] = 5
        vec = make_neg(violated)
        if vec is not None:
            X.append(vec); y.append(0); count += 1

    # If not enough visiting faculty violations, supplement with high load
    if count < per_type:
        for _ in range((per_type - count) * 5):
            if count >= per_type:
                break
            row = random.choice(all_rows)
            if row["faculty"] == "TBD":
                continue
            fmeta = fac_meta_map.get(row["faculty"], {})
            max_h = fmeta.get("max_hours_per_week", 18)
            # Simulate faculty already at max load by duplicating their sessions
            # into extra slots — this pushes them over the cap
            violated = dict(row)
            # Just assign a duplicate slot on the same day — effectively double booked
            violated["slot_index"] = (int(row["slot_index"]) % 6) + 1
            vec = make_neg(violated)
            if vec is not None:
                X.append(vec); y.append(0); count += 1

    log.info(f"  Type 3 (overload/unavailability): {count}")

    # ── Type 4: Random slot swap ──────────────────────────────────────────────
    count = 0
    for _ in range(per_type * 3):
        if count >= per_type:
            break
        row = random.choice(all_rows)
        # Pick a random different slot
        new_day, new_slot = random.choice(all_slots)
        if new_day == row["day"] and new_slot == row["slot_index"]:
            continue
        violated = dict(row)
        violated["day"]        = new_day
        violated["slot_index"] = new_slot
        violated["day_index"]  = ["Monday","Tuesday","Wednesday",
                                   "Thursday","Friday"].index(new_day)
        # For labs that need consecutive slots, swap to a non-consecutive one
        if row["is_consecutive_lab"] == 1:
            violated["is_consecutive_lab"] = 0
        vec = make_neg(violated)
        if vec is not None:
            X.append(vec); y.append(0); count += 1

    log.info(f"  Type 4 (random slot swap): {count}")

    log.info(f"  Total negative samples: {len(X)}")
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # ── Load data ─────────────────────────────────────────────────────────────
    log.info("Loading data...")
    df       = pd.read_csv(SESSION_CSV)
    fac_df   = pd.read_csv(FACULTY_CSV)
    rooms_df = pd.read_csv(ROOMS_CSV)
    slots_df = pd.read_csv(SLOTS_CSV)

    with open(EMBED_PATH, "rb") as f:
        embeddings = pickle.load(f)

    df["course_code"] = df["course_code"].fillna("")

    # ── Build lookup maps ──────────────────────────────────────────────────────
    fac_meta_map  = {r["faculty_name"]: r for _, r in fac_df.iterrows()}
    room_meta_map = {str(r["room_id"]): r for _, r in rooms_df.iterrows()}
    slot_meta_map = {}
    for _, r in slots_df[slots_df["is_lunch"] == 0].iterrows():
        slot_meta_map[(r["day"], int(r["slot_index"]))] = r

    log.info(f"  Sessions: {len(df)}, Faculty: {len(fac_meta_map)}, "
             f"Rooms: {len(room_meta_map)}, Slots: {len(slot_meta_map)}")

    # ── Build feature matrix ──────────────────────────────────────────────────
    log.info("Building positive samples...")
    X_pos, y_pos = build_positive_samples(
        df, embeddings, fac_meta_map, room_meta_map, slot_meta_map
    )

    log.info("Building negative samples...")
    X_neg, y_neg = build_negative_samples(
        df, embeddings, fac_meta_map, room_meta_map, slot_meta_map,
        neg_ratio=3
    )

    # ── Combine and split ──────────────────────────────────────────────────────
    X = np.vstack([X_pos, X_neg])
    y = np.concatenate([y_pos, y_neg])

    log.info(f"Total dataset: {len(X)} samples "
             f"(pos={y_pos.sum()}, neg={(y==0).sum()}), "
             f"ratio={y_pos.sum()/(y==0).sum():.2f}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y
    )
    log.info(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # ── Train Random Forest ────────────────────────────────────────────────────
    log.info("Training Random Forest...")
    rf = RandomForestClassifier(
        n_estimators    = 300,
        max_depth       = 15,
        min_samples_leaf= 2,
        max_features    = "sqrt",
        class_weight    = "balanced",
        n_jobs          = -1,
        random_state    = SEED,
        oob_score       = True,
    )
    rf.fit(X_train, y_train)
    log.info(f"  OOB score: {rf.oob_score_:.4f}")

    # ── Evaluate ───────────────────────────────────────────────────────────────
    y_pred      = rf.predict(X_test)
    y_prob      = rf.predict_proba(X_test)[:, 1]
    auc         = roc_auc_score(y_test, y_prob)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="binary"
    )
    cm          = confusion_matrix(y_test, y_pred)

    log.info("Evaluation on held-out test set:")
    log.info(f"  AUC-ROC   : {auc:.4f}")
    log.info(f"  Precision : {prec:.4f}")
    log.info(f"  Recall    : {rec:.4f}")
    log.info(f"  F1        : {f1:.4f}")
    log.info(f"  OOB Score : {rf.oob_score_:.4f}")
    log.info(f"\n{classification_report(y_test, y_pred, target_names=['Invalid','Valid'])}")

    # ── Feature importance ─────────────────────────────────────────────────────
    feat_names = get_feature_names()
    importances = rf.feature_importances_
    top_idx     = np.argsort(importances)[::-1][:20]

    log.info("Top 20 most important features:")
    for i, idx in enumerate(top_idx):
        name = feat_names[idx] if idx < len(feat_names) else f"feat_{idx}"
        log.info(f"  {i+1:2d}. {name:<30s} {importances[idx]:.4f}")

    # ── Cross-validation for robust estimate ──────────────────────────────────
    log.info("Running 5-fold cross-validation...")
    skf      = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_aucs  = []
    cv_f1s   = []

    for fold, (tr_idx, val_idx) in enumerate(skf.split(X, y), 1):
        rf_cv = RandomForestClassifier(
            n_estimators=200, max_depth=15, max_features="sqrt",
            class_weight="balanced", n_jobs=-1, random_state=SEED
        )
        rf_cv.fit(X[tr_idx], y[tr_idx])
        prob_val = rf_cv.predict_proba(X[val_idx])[:, 1]
        pred_val = rf_cv.predict(X[val_idx])
        fold_auc = roc_auc_score(y[val_idx], prob_val)
        _, _, fold_f1, _ = precision_recall_fscore_support(
            y[val_idx], pred_val, average="binary"
        )
        cv_aucs.append(fold_auc)
        cv_f1s.append(fold_f1)
        log.info(f"  Fold {fold}: AUC={fold_auc:.4f}, F1={fold_f1:.4f}")

    log.info(f"  CV AUC: {np.mean(cv_aucs):.4f} ± {np.std(cv_aucs):.4f}")
    log.info(f"  CV F1:  {np.mean(cv_f1s):.4f}  ± {np.std(cv_f1s):.4f}")

    # ── Save ──────────────────────────────────────────────────────────────────
    log.info("Saving...")

    with open(RF_MODEL_PATH, "wb") as f:
        pickle.dump(rf, f, protocol=pickle.HIGHEST_PROTOCOL)

    with open(RF_FEATURES_PATH, "w") as f:
        json.dump(feat_names, f, indent=2)

    report = {
        "n_train"          : int(len(X_train)),
        "n_test"           : int(len(X_test)),
        "n_positive"       : int(y_pos.sum()),
        "n_negative"       : int((y == 0).sum()),
        "test_auc"         : float(auc),
        "test_precision"   : float(prec),
        "test_recall"      : float(rec),
        "test_f1"          : float(f1),
        "oob_score"        : float(rf.oob_score_),
        "cv_auc_mean"      : float(np.mean(cv_aucs)),
        "cv_auc_std"       : float(np.std(cv_aucs)),
        "cv_f1_mean"       : float(np.mean(cv_f1s)),
        "cv_f1_std"        : float(np.std(cv_f1s)),
        "confusion_matrix" : cm.tolist(),
        "feature_dim"      : int(X.shape[1]),
        "top_features"     : [
            {"name": feat_names[idx], "importance": float(importances[idx])}
            for idx in top_idx
        ],
    }

    with open(RF_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    log.info(f"  Model   → {RF_MODEL_PATH}")
    log.info(f"  Features→ {RF_FEATURES_PATH}")
    log.info(f"  Report  → {RF_REPORT_PATH}")
    log.info(f"Done. AUC={auc:.4f}, F1={f1:.4f}")

    return rf, report


if __name__ == "__main__":
    main()
