"""
paper_metrics — produces every number reported in the TIMETRIX paper.

Outputs one JSON file (default: server/ml_pipeline/trained/paper_results.json)
with sections that map 1-to-1 to paper sections VI.A through VI.E.

Run order (do this BEFORE invoking this command):
    python manage.py run_pipeline           # trains GNN + RF, writes artefacts
    python manage.py paper_metrics --runs 10

What it does:
    1. Reads existing artefact JSONs (gnn_training_log.json, rf_training_report.json).
    2. Recomputes RF metrics that the training script does not emit (PR-AUC,
       precision, recall, F1, Brier) using the same feature-build pipeline.
    3. Recomputes embedding quality (within-group vs across-group cosine
       similarity for faculty grouped by designation, and rooms by lab/theory).
    4. Runs the SchedulerEngine N times against a target timetable, captures
       per-phase placement counts via a non-invasive timer wrapper, and records
       wall-clock timing per phase.
    5. Runs an INDEPENDENT post-hoc validator on the saved allocations of the
       last run — checks H1 through H7 hard constraints and reports violations.
    6. Aggregates everything into one paper-ready JSON.

File location:
    server/scheduler/management/commands/paper_metrics.py

Usage:
    python manage.py paper_metrics --runs 10 --timetable 3
    python manage.py paper_metrics --runs 10                 # auto-pick latest tt
    python manage.py paper_metrics --runs 5 --skip-rf-recompute
    python manage.py paper_metrics --out path/to/results.json
"""
import json
import platform
import statistics
import time
import traceback
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand, CommandError

from academics.models import AcademicTerm, CourseOffering
from faculty.models import Faculty
from infrastructure.models import Room
from scheduler.models import Timetable, TimeSlot, LectureAllocation
from scheduler.engine import SchedulerEngine
from scheduler.engine.constants import EMBED_PATH, RF_MODEL_PATH, RF_META_PATH

ML_DIR        = Path(EMBED_PATH).parent          # …/ml_pipeline/trained
GNN_LOG       = ML_DIR / "gnn_training_log.json"
RF_REPORT     = ML_DIR / "rf_training_report.json"
NODE_META     = ML_DIR / "node_metadata.pkl"
DEFAULT_OUT   = ML_DIR / "paper_results.json"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — HARDWARE / ENVIRONMENT
# ─────────────────────────────────────────────────────────────────────────────

def section_environment() -> dict:
    """Records the machine spec that produced the numbers."""
    try:
        import torch
        torch_version = torch.__version__
        cuda_available = torch.cuda.is_available()
        cuda_device = torch.cuda.get_device_name(0) if cuda_available else None
    except Exception:
        torch_version, cuda_available, cuda_device = None, False, None

    return {
        "timestamp"        : datetime.utcnow().isoformat() + "Z",
        "python_version"   : platform.python_version(),
        "platform"         : platform.platform(),
        "processor"        : platform.processor() or platform.machine(),
        "torch_version"    : torch_version,
        "cuda_available"   : cuda_available,
        "cuda_device"      : cuda_device,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — DATASET SUMMARY (counts straight from the operational DB)
# ─────────────────────────────────────────────────────────────────────────────

def section_dataset() -> dict:
    role_counts = Counter(Faculty.objects.values_list("role", flat=True))
    room_type_counts = Counter(Room.objects.values_list("room_type", flat=True))

    return {
        "faculty_total"        : Faculty.objects.count(),
        "faculty_by_role"      : dict(role_counts),
        "rooms_total"          : Room.objects.count(),
        "rooms_by_type"        : dict(room_type_counts),
        "course_offerings"     : CourseOffering.objects.count(),
        "academic_terms"       : AcademicTerm.objects.count(),
        "teaching_timeslots"   : TimeSlot.objects.filter(is_lunch=False).count(),
        "lunch_timeslots"      : TimeSlot.objects.filter(is_lunch=True).count(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — GNN TRAINING + EMBEDDING QUALITY
# ─────────────────────────────────────────────────────────────────────────────

def section_gnn() -> dict:
    out = {"source_file": str(GNN_LOG)}

    if not GNN_LOG.exists():
        out["error"] = "gnn_training_log.json not found — run train_gnn first."
        return out

    log = json.loads(GNN_LOG.read_text())
    history = log.get("history", [])

    out["epochs_run"]       = log.get("epochs_run")
    out["best_loss"]        = log.get("best_loss")
    out["final_loss"]       = history[-1]["loss"] if history else None
    out["final_acc"]        = log.get("final_acc")
    out["embedding_shape"]  = log.get("embedding_shape")
    out["validation_issues"] = log.get("validation_issues", [])

    # Loss curve summary (first / mid / last) — the paper figure renders from this
    if history:
        out["loss_curve"] = {
            "epoch_1"      : history[0]["loss"],
            "epoch_mid"    : history[len(history) // 2]["loss"],
            "epoch_last"   : history[-1]["loss"],
            "all_epochs"   : [{"epoch": h["epoch"], "loss": round(h["loss"], 4)}
                              for h in history],
        }

    out["embedding_quality"] = embedding_quality()
    return out


def embedding_quality() -> dict:
    """Within-group vs across-group cosine similarity for faculty + rooms.

    Faculty grouped by designation (Professor / Assoc Prof / Asst Prof / etc.).
    Rooms grouped by lab vs theory.

    Higher within-group similarity than across-group is what the paper claims,
    and is the standard sanity check that link prediction has learned a
    semantically meaningful embedding space.
    """
    import pickle

    out = {}
    if not Path(EMBED_PATH).exists() or not NODE_META.exists():
        out["error"] = "node_embeddings.pkl or node_metadata.pkl not found."
        return out

    with open(EMBED_PATH, "rb") as f:
        emb = pickle.load(f)
    with open(NODE_META, "rb") as f:
        meta = pickle.load(f)

    def cos(a, b):
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    def group_stats(node_keys_by_group):
        within, across = [], []
        groups = list(node_keys_by_group.keys())
        for i, g1 in enumerate(groups):
            keys1 = node_keys_by_group[g1]
            # within
            for ki in range(len(keys1)):
                for kj in range(ki + 1, len(keys1)):
                    within.append(cos(emb[keys1[ki]], emb[keys1[kj]]))
            # across
            for g2 in groups[i + 1:]:
                keys2 = node_keys_by_group[g2]
                for k1 in keys1:
                    for k2 in keys2:
                        across.append(cos(emb[k1], emb[k2]))
        return {
            "within_mean"   : round(float(np.mean(within)), 4) if within else None,
            "within_std"    : round(float(np.std(within)), 4) if within else None,
            "within_pairs"  : len(within),
            "across_mean"   : round(float(np.mean(across)), 4) if across else None,
            "across_std"    : round(float(np.std(across)), 4) if across else None,
            "across_pairs"  : len(across),
            "separation"    : (round(float(np.mean(within) - np.mean(across)), 4)
                               if within and across else None),
        }

    # Faculty grouped by designation
    fac_groups = defaultdict(list)
    for k, v in meta.items():
        if v.get("type") == "faculty" and k in emb:
            fac_groups[v.get("designation", "Unknown")].append(k)
    fac_groups = {g: ks for g, ks in fac_groups.items() if len(ks) >= 2}
    out["faculty_by_designation"] = group_stats(fac_groups) if fac_groups else \
        {"error": "Not enough faculty per designation group."}
    out["faculty_group_sizes"] = {g: len(ks) for g, ks in fac_groups.items()}

    # Rooms grouped by lab/theory
    room_groups = defaultdict(list)
    for k, v in meta.items():
        if v.get("type") == "room" and k in emb:
            label = "lab" if v.get("is_lab") == 1 else "theory"
            room_groups[label].append(k)
    room_groups = {g: ks for g, ks in room_groups.items() if len(ks) >= 2}
    out["rooms_by_type"] = group_stats(room_groups) if room_groups else \
        {"error": "Not enough rooms of each type."}
    out["room_group_sizes"] = {g: len(ks) for g, ks in room_groups.items()}

    return out


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — RANDOM FOREST + GRADIENT BOOSTING ENSEMBLE
# ─────────────────────────────────────────────────────────────────────────────

def section_rf(skip_recompute: bool = False) -> dict:
    out = {"source_file": str(RF_REPORT)}

    if RF_REPORT.exists():
        report = json.loads(RF_REPORT.read_text())
        out["from_training_report"] = report
    else:
        out["from_training_report"] = {"error": "rf_training_report.json missing."}

    if skip_recompute:
        out["recomputed"] = {"skipped": True}
        return out

    out["recomputed"] = recompute_rf_metrics()
    return out


def recompute_rf_metrics() -> dict:
    """Rebuild X, y exactly the way RF training does and run a 5-fold
    stratified CV with the full set of metrics the paper reports.

    This is slow (~2-5 minutes) but produces ROC-AUC, PR-AUC, accuracy,
    precision, recall, F1, and Brier with proper mean ± std.
    """
    import pickle
    import pandas as pd
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import (
        roc_auc_score, average_precision_score, accuracy_score,
        precision_score, recall_score, f1_score, brier_score_loss,
    )
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import VotingClassifier
    from sklearn.preprocessing import StandardScaler

    try:
        from ml_pipeline.random_forest_model import (
            SESSION_CSV, FACULTY_CSV, ROOMS_CSV, SEED,
            compute_stats, build_positive_samples, build_negative_samples,
        )
    except Exception as e:
        return {"error": f"Could not import RF helpers: {e}"}

    if not Path(EMBED_PATH).exists():
        return {"error": "node_embeddings.pkl missing — train GNN first."}

    try:
        df         = pd.read_csv(SESSION_CSV)
        faculty_df = pd.read_csv(FACULTY_CSV)
        rooms_df   = pd.read_csv(ROOMS_CSV)
        df["course_code"] = df["course_code"].fillna("")
        rooms_df["lab_type"] = rooms_df["lab_type"].fillna("")
    except Exception as e:
        return {"error": f"Could not load data CSVs: {e}"}

    with open(EMBED_PATH, "rb") as f:
        embeddings = pickle.load(f)

    max_hours_map = {
        r["faculty_name"]: r["max_hours_per_week"]
        for _, r in faculty_df.iterrows()
    }
    stats = compute_stats(df)

    X_pos, y_pos = build_positive_samples(df, embeddings, max_hours_map, stats)
    n_neg = len(y_pos) * 3
    X_neg, y_neg = build_negative_samples(
        df, embeddings, max_hours_map, stats, rooms_df, faculty_df, n_neg
    )

    X = np.vstack([X_pos, X_neg])
    y = np.concatenate([y_pos, y_neg])
    rng = np.random.default_rng(SEED)
    idx = rng.permutation(len(y))
    X, y = X[idx], y[idx]

    # Reproducing the same ensemble the training script builds.
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    metrics = defaultdict(list)

    for fold, (tr, te) in enumerate(skf.split(X, y), start=1):
        sc = StandardScaler().fit(X[tr])
        Xtr, Xte = sc.transform(X[tr]), sc.transform(X[te])

        rf = RandomForestClassifier(
            n_estimators=200, max_depth=12, class_weight="balanced",
            oob_score=True, n_jobs=-1, random_state=SEED,
        )
        rf_cal = CalibratedClassifierCV(rf, method="isotonic", cv=3)
        gb = GradientBoostingClassifier(
            n_estimators=100, learning_rate=0.05, max_depth=4,
            random_state=SEED,
        )
        ens = VotingClassifier(
            estimators=[("rf", rf_cal), ("gb", gb)], voting="soft",
        )
        ens.fit(Xtr, y[tr])
        proba = ens.predict_proba(Xte)[:, 1]
        pred  = (proba >= 0.5).astype(int)

        metrics["roc_auc"].append(roc_auc_score(y[te], proba))
        metrics["pr_auc"].append(average_precision_score(y[te], proba))
        metrics["accuracy"].append(accuracy_score(y[te], pred))
        metrics["precision"].append(precision_score(y[te], pred, zero_division=0))
        metrics["recall"].append(recall_score(y[te], pred, zero_division=0))
        metrics["f1"].append(f1_score(y[te], pred, zero_division=0))
        metrics["brier"].append(brier_score_loss(y[te], proba))

    summary = {}
    for m, vals in metrics.items():
        summary[m] = {
            "mean"   : round(float(np.mean(vals)), 4),
            "std"    : round(float(np.std(vals)), 4),
            "folds"  : [round(float(v), 4) for v in vals],
        }
    summary["n_total"]     = int(len(y))
    summary["n_positives"] = int(y.sum())
    summary["n_negatives"] = int((y == 0).sum())
    summary["pos_neg_ratio"] = round(float(y.sum() / max(1, (y == 0).sum())), 3)
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — SCHEDULER BENCHMARK (per-phase placement + timing)
# ─────────────────────────────────────────────────────────────────────────────

def _wrap_timer_for_phase_tracking(engine):
    """Replace engine.timer.phase with a wrapper that, after each phase
    completes, records len(engine.pending_saves) so we can build Table II.

    Non-invasive: the original timer behaviour (perf_counter, log lines) is
    fully preserved.
    """
    original_phase = engine.timer.phase
    placements = {}

    @contextmanager
    def tracking_phase(name):
        with original_phase(name):
            yield
        placements[name] = len(engine.pending_saves)

    engine.timer.phase = tracking_phase
    return placements


def _benchmark_one_run(timetable_id: int) -> dict:
    """Clear the timetable, run the engine once, return everything we need."""
    LectureAllocation.objects.filter(timetable_id=timetable_id).delete()

    t0 = time.perf_counter()
    engine = SchedulerEngine(timetable_id=timetable_id)
    placement_by_phase = _wrap_timer_for_phase_tracking(engine)
    result = engine.run()
    wall_total = time.perf_counter() - t0

    saved_count = LectureAllocation.objects.filter(timetable_id=timetable_id).count()
    expected = CourseOffering.objects.filter(
        student_group__term=engine.term
    ).count()

    return {
        "status"               : result.get("status"),
        "ml_used"              : result.get("ml_used", False),
        "expected_offerings"   : expected,
        "saved_allocations"    : saved_count,
        "in_memory_allocations": result.get("allocations", 0),
        "unscheduled_count"    : len(result.get("unscheduled", [])),
        "avg_score"            : result.get("avg_score"),
        "phase_timings"        : result.get("timings", {}),
        "phase_placements"     : placement_by_phase,
        "wall_total"           : round(wall_total, 3),
        "rejection_top"        : result.get("rejection_top", []),
    }


def section_scheduler(timetable_id: int, runs: int) -> dict:
    """Run the scheduler `runs` times. Returns aggregated stats + per-run rows."""
    all_runs = []
    for i in range(1, runs + 1):
        try:
            r = _benchmark_one_run(timetable_id)
            r["run"] = i
            all_runs.append(r)
            print(f"  [run {i}/{runs}] status={r['status']:<8s} "
                  f"saved={r['saved_allocations']:<4d} "
                  f"unsched={r['unscheduled_count']:<3d} "
                  f"time={r['wall_total']:.2f}s", flush=True)
        except Exception as e:
            print(f"  [run {i}/{runs}] FAILED: {e}", flush=True)
            all_runs.append({"run": i, "error": str(e),
                             "traceback": traceback.format_exc()})

    successful = [r for r in all_runs if "error" not in r]
    if not successful:
        return {"runs_attempted": runs, "successful": 0, "all_runs": all_runs,
                "error": "All runs failed."}

    # Aggregate over successful runs
    def agg(key, transform=lambda x: x):
        vals = [transform(r[key]) for r in successful if key in r]
        if not vals:
            return None
        return {
            "mean": round(float(np.mean(vals)), 3),
            "std" : round(float(np.std(vals)), 3),
            "min" : round(float(np.min(vals)), 3),
            "max" : round(float(np.max(vals)), 3),
        }

    # Phase-level placement aggregation (Table II in the paper)
    phase_names = sorted({p for r in successful for p in r["phase_placements"]})
    phase_placement_agg = {}
    for ph in phase_names:
        vals = [r["phase_placements"].get(ph, 0) for r in successful]
        phase_placement_agg[ph] = {
            "mean"  : round(float(np.mean(vals)), 2),
            "std"   : round(float(np.std(vals)), 2),
            "min"   : int(np.min(vals)),
            "max"   : int(np.max(vals)),
            "values": [int(v) for v in vals],
        }

    # Phase-level timing aggregation
    timing_keys = sorted({k for r in successful for k in r["phase_timings"]})
    phase_timing_agg = {}
    total_time = float(np.mean([r["wall_total"] for r in successful]))
    for ph in timing_keys:
        vals = [r["phase_timings"].get(ph, 0.0) for r in successful]
        phase_timing_agg[ph] = {
            "mean_seconds"   : round(float(np.mean(vals)), 3),
            "std_seconds"    : round(float(np.std(vals)), 3),
            "pct_of_total"   : round(float(np.mean(vals)) / total_time * 100, 2)
                               if total_time > 0 else None,
        }

    expected = successful[0]["expected_offerings"]
    saved_vals = [r["saved_allocations"] for r in successful]
    runs_at_100pct = sum(1 for v in saved_vals if v >= expected)

    return {
        "runs_attempted" : runs,
        "runs_successful": len(successful),
        "expected_offerings"          : expected,
        "saved_allocations"           : agg("saved_allocations"),
        "unscheduled_count"           : agg("unscheduled_count"),
        "wall_total_seconds"          : agg("wall_total"),
        "avg_score"                   : agg("avg_score"),
        "runs_at_100_percent"         : runs_at_100pct,
        "runs_at_100_percent_fraction": f"{runs_at_100pct}/{len(successful)}",
        "phase_placements_aggregated" : phase_placement_agg,
        "phase_timings_aggregated"    : phase_timing_agg,
        "all_runs"                    : all_runs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — INDEPENDENT HARD-CONSTRAINT VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

def section_validator(timetable_id: int) -> dict:
    """Post-hoc check on whatever LectureAllocations exist for `timetable_id`.

    Verifies H1-H7 by iterating saved rows. Independent of the engine -- does
    not import scheduler.engine at all.

    PE-aware: Parallel Elective (PE) courses intentionally share a timeslot
    across multiple sections (different rooms, different faculty, same student
    group pool). Conflicts where ALL involved allocations are PE electives are
    exempted from H1/H2/H3 since that is the correct scheduling behaviour.
    """
    allocs = list(
        LectureAllocation.objects.filter(timetable_id=timetable_id)
        .select_related(
            "faculty", "room", "timeslot", "student_group",
            "course_offering__course",
        )
    )

    violations = defaultdict(list)

    # Build PE alloc-id set for exemption checks
    pe_alloc_ids = {
        a.id for a in allocs
        if a.course_offering.course.course_type == "PE"
    }

    def _all_pe(ids):
        """True when every alloc in the list is a PE elective."""
        return all(aid in pe_alloc_ids for aid in ids)

    # H1 -- no faculty in two places at the same time
    by_fac_slot = defaultdict(list)
    for a in allocs:
        if a.faculty_id is None:
            continue
        by_fac_slot[(a.faculty_id, a.timeslot_id)].append(a.id)
    for (fid, sid), ids in by_fac_slot.items():
        if len(ids) > 1 and not _all_pe(ids):
            violations["H1_faculty_double_book"].append({
                "faculty_id": fid, "timeslot_id": sid, "alloc_ids": ids,
            })

    # H2 -- no room in two places at the same time
    by_room_slot = defaultdict(list)
    for a in allocs:
        by_room_slot[(a.room_id, a.timeslot_id)].append(a.id)
    for (rid, sid), ids in by_room_slot.items():
        if len(ids) > 1 and not _all_pe(ids):
            violations["H2_room_double_book"].append({
                "room_id": rid, "timeslot_id": sid, "alloc_ids": ids,
            })

    # H3 -- no student group in two places at the same time
    by_sg_slot = defaultdict(list)
    for a in allocs:
        by_sg_slot[(a.student_group_id, a.timeslot_id)].append(a.id)
    for (sgid, sid), ids in by_sg_slot.items():
        if len(ids) > 1 and not _all_pe(ids):
            violations["H3_group_double_book"].append({
                "student_group_id": sgid, "timeslot_id": sid, "alloc_ids": ids,
            })

    # H4 -- faculty weekly cap not exceeded
    fac_load = Counter()
    for a in allocs:
        if a.faculty_id is not None:
            fac_load[a.faculty_id] += 1
    fac_caps = dict(Faculty.objects.values_list("id", "max_weekly_load"))
    for fid, count in fac_load.items():
        cap = fac_caps.get(fid)
        if cap is not None and count > cap:
            violations["H4_faculty_overload"].append({
                "faculty_id": fid, "load": count, "cap": cap,
            })

    # H5 -- lab course must use lab room; theory must use theory room
    for a in allocs:
        course = a.course_offering.course
        if course.requires_lab_room and a.room.room_type != "LAB":
            violations["H5_lab_in_theory_room"].append({
                "alloc_id": a.id, "course": course.code, "room": str(a.room),
            })
        if (not course.requires_lab_room) and a.room.room_type == "LAB":
            violations["H5_warn_theory_in_lab"].append({
                "alloc_id": a.id, "course": course.code, "room": str(a.room),
            })

    # H6 -- labs must occupy 2 consecutive slots on the same day
    lab_offerings = defaultdict(list)
    for a in allocs:
        if a.course_offering.course.requires_consecutive_slots:
            lab_offerings[a.course_offering_id].append(a)
    for off_id, rows in lab_offerings.items():
        by_day = defaultdict(list)
        for a in rows:
            by_day[a.timeslot.day].append(a.timeslot.slot_number)
        ok_pairs = 0
        for day, slots in by_day.items():
            slots.sort()
            for i in range(len(slots) - 1):
                if slots[i + 1] == slots[i] + 1:
                    ok_pairs += 1
        if len(rows) >= 2 and ok_pairs == 0:
            violations["H6_lab_not_consecutive"].append({
                "offering_id": off_id,
                "slot_distribution": [
                    {"day": a.timeslot.day, "slot": a.timeslot.slot_number}
                    for a in rows
                ],
            })
        elif len(rows) < 2:
            violations["H6_lab_missing_pair"].append({
                "offering_id": off_id, "rows_found": len(rows),
            })

    # H7 -- no allocation in lunch slot
    for a in allocs:
        if a.timeslot.is_lunch:
            violations["H7_lunch_violation"].append({
                "alloc_id": a.id, "timeslot_id": a.timeslot_id,
            })

    summary = {k: len(v) for k, v in violations.items()}
    total = sum(summary.values())
    return {
        "timetable_id"     : timetable_id,
        "allocations_checked": len(allocs),
        "total_violations" : total,
        "violations_by_type": summary,
        "pe_allocs_detected": len(pe_alloc_ids),
        "details"          : dict(violations) if total > 0 else {},
        "verdict"          : "PASS" if total == 0 else "FAIL",
    }


# ─────────────────────────────────────────────────────────────────────────────
# DJANGO COMMAND
# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Produce every paper number in a single JSON report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--runs", type=int, default=10,
            help="Scheduler benchmark runs (default 10).")
        parser.add_argument(
            "--timetable", type=int, default=None,
            help="Timetable id to benchmark on. Default: latest in DB.")
        parser.add_argument(
            "--out", type=str, default=str(DEFAULT_OUT),
            help=f"Output JSON path (default {DEFAULT_OUT}).")
        parser.add_argument(
            "--skip-rf-recompute", action="store_true",
            help="Skip the slow CV recomputation; use rf_training_report.json only.")
        parser.add_argument(
            "--skip-scheduler", action="store_true",
            help="Skip scheduler benchmark (useful for fast ML-only metrics).")

    def handle(self, *args, **opts):
        result = {}

        # --- Section 1
        self.stdout.write("[1/6] Recording environment...")
        result["environment"] = section_environment()

        # --- Section 2
        self.stdout.write("[2/6] Summarising dataset...")
        result["dataset"] = section_dataset()

        # --- Section 3
        self.stdout.write("[3/6] Reading GNN training log + computing embedding quality...")
        result["gnn"] = section_gnn()

        # --- Section 4
        if opts["skip_rf_recompute"]:
            self.stdout.write("[4/6] Reading RF report (skipping CV recompute)...")
        else:
            self.stdout.write("[4/6] Reading RF report + recomputing 5-fold CV "
                              "(this takes 2–5 minutes)...")
        result["rf_ensemble"] = section_rf(skip_recompute=opts["skip_rf_recompute"])

        # --- Section 5
        if opts["skip_scheduler"]:
            self.stdout.write("[5/6] Skipping scheduler benchmark.")
            result["scheduler"] = {"skipped": True}
            tt_id = None
        else:
            tt_id = opts["timetable"]
            if tt_id is None:
                latest = Timetable.objects.order_by("-created_at").first()
                if latest is None:
                    raise CommandError(
                        "No Timetable rows in DB. Pass --timetable <id> "
                        "or generate one first.")
                tt_id = latest.id
                self.stdout.write(f"   Using latest timetable id={tt_id}")

            self.stdout.write(f"[5/6] Benchmarking scheduler "
                              f"({opts['runs']} runs on timetable {tt_id})...")
            result["scheduler"] = section_scheduler(tt_id, opts["runs"])

        # --- Section 6
        if tt_id is not None and not opts["skip_scheduler"]:
            self.stdout.write("[6/6] Running independent constraint validator...")
            result["validator"] = section_validator(tt_id)
        else:
            result["validator"] = {"skipped": True}

        # --- Write
        out_path = Path(opts["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, default=str))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Wrote {out_path}\n"))
        self._print_paper_cheatsheet(result)

    # ─────────────────────────────────────────────────────────────────────────
    # Cheat sheet — prints the lines you literally paste into the paper
    # ─────────────────────────────────────────────────────────────────────────

    def _print_paper_cheatsheet(self, r: dict):
        self.stdout.write("=" * 70)
        self.stdout.write(" PAPER NUMBERS -- paste-ready")
        self.stdout.write("=" * 70)

        ds = r.get("dataset", {})
        self.stdout.write(
            f"VI.A Dataset: {ds.get('faculty_total')} faculty, "
            f"{ds.get('course_offerings')} offerings, "
            f"{ds.get('rooms_total')} rooms, "
            f"{ds.get('teaching_timeslots')} teaching timeslots.")

        gnn = r.get("gnn", {})
        if "epochs_run" in gnn:
            self.stdout.write(
                f"VI.B GNN: trained for {gnn['epochs_run']} epochs, "
                f"best loss {gnn.get('best_loss')}, "
                f"final loss {gnn.get('final_loss')}, "
                f"final acc {gnn.get('final_acc')}.")
            eq = gnn.get("embedding_quality", {})
            fac_eq = eq.get("faculty_by_designation", {})
            if fac_eq.get("within_mean") is not None:
                self.stdout.write(
                    f"     Embedding quality (faculty by designation): "
                    f"within={fac_eq['within_mean']}, "
                    f"across={fac_eq['across_mean']}, "
                    f"separation={fac_eq['separation']}.")

        rf = r.get("rf_ensemble", {}).get("recomputed", {})
        if "roc_auc" in rf:
            def line(k, label):
                m = rf[k]
                return f"{label}={m['mean']}+/-{m['std']}"
            self.stdout.write(
                "VI.C RF Ensemble (5-fold CV): " +
                ", ".join([
                    line("roc_auc", "ROC-AUC"),
                    line("pr_auc",  "PR-AUC"),
                    line("accuracy", "Acc"),
                    line("precision", "Prec"),
                    line("recall", "Rec"),
                    line("f1", "F1"),
                    line("brier", "Brier"),
                ]))
            self.stdout.write(
                f"     Class balance: {rf.get('n_positives')} positives, "
                f"{rf.get('n_negatives')} negatives.")

        sc = r.get("scheduler", {})
        if "saved_allocations" in sc:
            sa, wt = sc["saved_allocations"], sc["wall_total_seconds"]
            self.stdout.write(
                f"VI.D Scheduler ({sc['runs_successful']} runs, "
                f"{sc['expected_offerings']} expected offerings):")
            self.stdout.write(
                f"     Mean placement: {sa['mean']} "
                f"(range {int(sa['min'])}-{int(sa['max'])}). "
                f"100% in {sc['runs_at_100_percent_fraction']} runs.")
            self.stdout.write(
                f"VI.E Runtime: mean {wt['mean']}s +/- {wt['std']}s "
                f"(range {wt['min']}-{wt['max']}s).")

            timings = sc.get("phase_timings_aggregated", {})
            if timings:
                top_phase = max(
                    [(k, v["pct_of_total"]) for k, v in timings.items()
                     if v["pct_of_total"] is not None],
                    key=lambda kv: kv[1], default=(None, 0))
                if top_phase[0]:
                    self.stdout.write(
                        f"     Hottest phase: {top_phase[0]} "
                        f"~{top_phase[1]}% of runtime.")

        v = r.get("validator", {})
        if "verdict" in v:
            mark = "PASS" if v["verdict"] == "PASS" else "FAIL"
            self.stdout.write(
                f"     Hard-constraint validator: {mark} "
                f"({v['total_violations']} violations across "
                f"{v['allocations_checked']} allocations).")

        self.stdout.write("=" * 70)
