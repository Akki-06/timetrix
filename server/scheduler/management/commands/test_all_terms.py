"""
test_all_terms — run the scheduler engine on EVERY AcademicTerm in the
database and validate each one independently.

Usage:
    python manage.py test_all_terms
    python manage.py test_all_terms --limit 10        # first 10 terms
    python manage.py test_all_terms --out results.json # save JSON report

Produces a table showing PASS/FAIL per program+semester+section, plus a
JSON report if --out is given.
"""
import json
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academics.models import AcademicTerm, CourseOffering, StudentGroup
from faculty.models import Faculty
from infrastructure.models import Room
from scheduler.models import Timetable, TimeSlot, LectureAllocation
from scheduler.engine import SchedulerEngine


def validate_timetable(timetable_id: int) -> dict:
    """PE-aware post-hoc validator.

    Same H1–H7 checks as paper_metrics, but recognises that PE elective
    offerings INTENTIONALLY share a timeslot across multiple sections.
    A PE allocation is identified by its CourseOffering → Course.course_type == 'PE'.
    """
    allocs = list(
        LectureAllocation.objects.filter(timetable_id=timetable_id)
        .select_related(
            "faculty", "room", "timeslot", "student_group",
            "course_offering__course",
        )
    )

    violations = defaultdict(list)

    # Build a quick lookup: timeslot_id → set of alloc ids that are PE
    pe_alloc_ids = {
        a.id for a in allocs
        if a.course_offering.course.course_type == "PE"
    }

    def is_all_pe(ids):
        """True if every allocation in `ids` is a PE elective."""
        return all(aid in pe_alloc_ids for aid in ids)

    # H1 — no faculty in two places at the same time (skip PE-vs-PE)
    by_fac_slot = defaultdict(list)
    for a in allocs:
        if a.faculty_id is None:
            continue
        by_fac_slot[(a.faculty_id, a.timeslot_id)].append(a.id)
    for (fid, sid), ids in by_fac_slot.items():
        if len(ids) > 1 and not is_all_pe(ids):
            violations["H1_faculty_double_book"].append({
                "faculty_id": fid, "timeslot_id": sid, "alloc_ids": ids,
            })

    # H2 — no room in two places at the same time (skip PE-vs-PE)
    by_room_slot = defaultdict(list)
    for a in allocs:
        by_room_slot[(a.room_id, a.timeslot_id)].append(a.id)
    for (rid, sid), ids in by_room_slot.items():
        if len(ids) > 1 and not is_all_pe(ids):
            violations["H2_room_double_book"].append({
                "room_id": rid, "timeslot_id": sid, "alloc_ids": ids,
            })

    # H3 — no student group in two places at the same time
    # PE electives: each PE option maps to the same combined group (A+B) but
    # students only attend ONE option → the group overlap is by design.
    by_sg_slot = defaultdict(list)
    for a in allocs:
        by_sg_slot[(a.student_group_id, a.timeslot_id)].append(a.id)
    for (sgid, sid), ids in by_sg_slot.items():
        if len(ids) > 1 and not is_all_pe(ids):
            violations["H3_group_double_book"].append({
                "student_group_id": sgid, "timeslot_id": sid, "alloc_ids": ids,
            })

    # H4 — faculty weekly cap not exceeded
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

    # H5 — lab course must use lab room
    for a in allocs:
        course = a.course_offering.course
        if course.requires_lab_room and a.room.room_type != "LAB":
            violations["H5_lab_in_theory_room"].append({
                "alloc_id": a.id, "course": course.code, "room": str(a.room),
            })

    # H6 — labs must occupy 2 consecutive slots on the same day
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
            })
        elif len(rows) < 2:
            violations["H6_lab_missing_pair"].append({
                "offering_id": off_id, "rows_found": len(rows),
            })

    # H7 — no allocation in lunch slot
    for a in allocs:
        if a.timeslot.is_lunch:
            violations["H7_lunch_violation"].append({
                "alloc_id": a.id, "timeslot_id": a.timeslot_id,
            })

    summary = {k: len(v) for k, v in violations.items()}
    total = sum(summary.values())
    return {
        "timetable_id": timetable_id,
        "allocations_checked": len(allocs),
        "total_violations": total,
        "violations_by_type": summary,
        "details": dict(violations) if total > 0 else {},
        "verdict": "PASS" if total == 0 else "FAIL",
    }


class Command(BaseCommand):
    help = "Run the scheduler on every AcademicTerm and validate each output."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Max number of terms to test (default: all).",
        )
        parser.add_argument(
            "--out", type=str, default=None,
            help="Optional path to save JSON results.",
        )

    def handle(self, *args, **opts):
        terms = list(
            AcademicTerm.objects.select_related("program")
            .order_by("program__code", "semester")
        )

        if not terms:
            raise CommandError("No AcademicTerm rows in the database.")

        if opts["limit"]:
            terms = terms[: opts["limit"]]

        # Quick summary of what we'll test
        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(f"  TIMETRIX FULL SYSTEM TEST — {len(terms)} program-semester combinations")
        self.stdout.write(f"{'='*80}\n")

        results = []
        pass_count = 0
        fail_count = 0
        error_count = 0

        for i, term in enumerate(terms, 1):
            program = term.program
            label = f"{program.code} Sem-{term.semester}"

            # Count offerings and sections for this term
            offerings = CourseOffering.objects.filter(
                student_group__term=term
            )
            n_offerings = offerings.count()
            sections = list(
                StudentGroup.objects.filter(term=term)
                .values_list("name", flat=True)
            )
            n_sections = len(sections)

            if n_offerings == 0:
                self.stdout.write(
                    f"  [{i:2d}/{len(terms)}] {label:30s} "
                    f"| SKIP (no offerings)"
                )
                results.append({
                    "term_id": term.id,
                    "program": program.code,
                    "program_name": program.display_name,
                    "semester": term.semester,
                    "sections": sections,
                    "offerings": 0,
                    "status": "SKIP",
                    "reason": "no offerings",
                })
                continue

            # Create a fresh timetable for this term
            try:
                existing_versions = Timetable.objects.filter(term=term).count()
                tt = Timetable.objects.create(
                    term=term,
                    version=existing_versions + 1,
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  [{i:2d}/{len(terms)}] {label:30s} "
                        f"| ERROR creating timetable: {e}"
                    )
                )
                error_count += 1
                results.append({
                    "term_id": term.id,
                    "program": program.code,
                    "program_name": program.display_name,
                    "semester": term.semester,
                    "sections": sections,
                    "offerings": n_offerings,
                    "status": "ERROR",
                    "error": str(e),
                })
                continue

            # Run the scheduler
            try:
                t0 = time.perf_counter()
                engine = SchedulerEngine(timetable_id=tt.id)
                result = engine.run()
                wall_time = time.perf_counter() - t0
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  [{i:2d}/{len(terms)}] {label:30s} "
                        f"| ENGINE ERROR: {e}"
                    )
                )
                error_count += 1
                results.append({
                    "term_id": term.id,
                    "program": program.code,
                    "program_name": program.display_name,
                    "semester": term.semester,
                    "sections": sections,
                    "offerings": n_offerings,
                    "timetable_id": tt.id,
                    "status": "ERROR",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })
                continue

            # Count what was placed
            saved = LectureAllocation.objects.filter(timetable_id=tt.id).count()
            unscheduled = len(result.get("unscheduled", []))
            ml_used = result.get("ml_used", False)

            # Validate
            try:
                validation = validate_timetable(tt.id)
            except Exception as e:
                validation = {"verdict": "ERROR", "error": str(e)}

            verdict = validation.get("verdict", "ERROR")
            violations = validation.get("total_violations", "?")

            if verdict == "PASS":
                pass_count += 1
                style = self.style.SUCCESS
                mark = "[PASS]"
            elif verdict == "FAIL":
                fail_count += 1
                style = self.style.ERROR
                mark = "[FAIL]"
            else:
                error_count += 1
                style = self.style.WARNING
                mark = "[ERR] "

            self.stdout.write(style(
                f"  [{i:2d}/{len(terms)}] {label:30s} "
                f"| {mark:8s} | sections={n_sections} "
                f"| offerings={n_offerings:3d} | saved={saved:3d} "
                f"| unsched={unscheduled} "
                f"| violations={violations} "
                f"| ml={'Y' if ml_used else 'N'} "
                f"| {wall_time:.2f}s"
            ))

            results.append({
                "term_id": term.id,
                "program": program.code,
                "program_name": program.display_name,
                "semester": term.semester,
                "sections": sections,
                "offerings": n_offerings,
                "timetable_id": tt.id,
                "status": result.get("status"),
                "ml_used": ml_used,
                "saved_allocations": saved,
                "unscheduled_count": unscheduled,
                "unscheduled_items": result.get("unscheduled", []),
                "avg_score": result.get("avg_score"),
                "wall_time_seconds": round(wall_time, 3),
                "validation": validation,
            })

        # ── Summary ──────────────────────────────────────────────────────────
        tested = pass_count + fail_count + error_count
        skipped = len(results) - tested

        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(f"  SUMMARY")
        self.stdout.write(f"{'='*80}")
        self.stdout.write(f"  Total terms:   {len(terms)}")
        self.stdout.write(f"  Tested:        {tested}")
        self.stdout.write(f"  Skipped:       {skipped} (no offerings)")
        self.stdout.write(self.style.SUCCESS(f"  PASSED:       {pass_count}"))
        if fail_count:
            self.stdout.write(self.style.ERROR(f"  FAILED:       {fail_count}"))
        else:
            self.stdout.write(f"  FAILED:       0")
        if error_count:
            self.stdout.write(self.style.WARNING(f"  ERRORS:       {error_count}"))
        else:
            self.stdout.write(f"  ERRORS:       0")

        # Total allocations
        total_saved = sum(
            r.get("saved_allocations", 0) for r in results if r.get("saved_allocations")
        )
        total_unsched = sum(
            r.get("unscheduled_count", 0) for r in results if isinstance(r.get("unscheduled_count"), int)
        )
        self.stdout.write(f"\n  Total allocations placed: {total_saved}")
        self.stdout.write(f"  Total unscheduled:        {total_unsched}")

        if tested > 0 and fail_count == 0 and error_count == 0:
            self.stdout.write(self.style.SUCCESS(
                f"\n  >>> ALL {tested} TESTS PASSED -- system is working correctly!"
            ))
        self.stdout.write(f"{'='*80}\n")

        # ── Save JSON ────────────────────────────────────────────────────────
        if opts["out"]:
            out_path = Path(opts["out"])
        else:
            out_path = (
                Path(__file__).resolve().parent.parent.parent.parent
                / "ml_pipeline" / "trained" / "test_all_terms_results.json"
            )

        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "terms_total": len(terms),
            "tested": tested,
            "skipped": skipped,
            "passed": pass_count,
            "failed": fail_count,
            "errors": error_count,
            "total_allocations": total_saved,
            "total_unscheduled": total_unsched,
            "results": results,
        }

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, default=str))
        self.stdout.write(f"  Report saved to: {out_path}\n")
