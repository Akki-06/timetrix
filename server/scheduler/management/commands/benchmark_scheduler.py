"""
benchmark_scheduler — run the scheduler N times on an existing timetable and
write a JSON report of timings, allocation counts, and rejection summaries.

Usage:
    python manage.py benchmark_scheduler --timetable 3 --runs 5
    python manage.py benchmark_scheduler --timetable 3 --runs 5 --out out/bench.json
"""
import json
import statistics
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from scheduler.engine import SchedulerEngine
from scheduler.models import Timetable, LectureAllocation


class Command(BaseCommand):
    help = "Benchmark the scheduler engine over multiple runs."

    def add_arguments(self, parser):
        parser.add_argument("--timetable", type=int, required=True,
                            help="Timetable id to (re)generate.")
        parser.add_argument("--runs", type=int, default=3,
                            help="Number of benchmark runs (default: 3).")
        parser.add_argument("--out", type=str, default=None,
                            help="Optional path to write a JSON report.")
        parser.add_argument("--keep", action="store_true",
                            help="Keep the final allocations instead of truncating.")

    def handle(self, *args, **opts):
        tt_id = opts["timetable"]
        runs  = opts["runs"]
        try:
            Timetable.objects.get(pk=tt_id)
        except Timetable.DoesNotExist:
            raise CommandError(f"Timetable id={tt_id} not found.")

        results = []
        for i in range(1, runs + 1):
            LectureAllocation.objects.filter(timetable_id=tt_id).delete()
            engine = SchedulerEngine(timetable_id=tt_id)
            out = engine.run()
            results.append({
                "run"         : i,
                "status"      : out.get("status"),
                "allocations" : out.get("allocations", 0),
                "avg_score"   : out.get("avg_score", 0.0),
                "unscheduled" : len(out.get("unscheduled", [])),
                "timings"     : out.get("timings", {}),
                "rejection_top": out.get("rejection_top", []),
            })
            self.stdout.write(
                f"  run {i}: status={out.get('status')} "
                f"saved={out.get('allocations')} "
                f"total={out.get('timings', {}).get('total', 0):.2f}s"
            )

        if not opts["keep"]:
            LectureAllocation.objects.filter(timetable_id=tt_id).delete()

        totals = [r["timings"].get("total", 0.0) for r in results]
        summary = {
            "timetable"   : tt_id,
            "runs"        : runs,
            "mean_total"  : round(statistics.mean(totals), 3) if totals else 0,
            "stdev_total" : round(statistics.stdev(totals), 3) if len(totals) > 1 else 0,
            "mean_saved"  : round(statistics.mean(r["allocations"] for r in results), 2),
            "results"     : results,
        }

        if opts["out"]:
            path = Path(opts["out"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(summary, indent=2))
            self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))
        else:
            self.stdout.write(json.dumps(summary, indent=2))
