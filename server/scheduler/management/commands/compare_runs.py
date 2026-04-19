"""
compare_runs — diff two benchmark JSON files (saved by benchmark_scheduler).

Usage:
    python manage.py compare_runs --a out/before.json --b out/after.json
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise CommandError(f"{path} not found")
    return json.loads(p.read_text())


class Command(BaseCommand):
    help = "Compare two benchmark JSON reports."

    def add_arguments(self, parser):
        parser.add_argument("--a", required=True, help="Baseline report path.")
        parser.add_argument("--b", required=True, help="New report path.")

    def handle(self, *args, **opts):
        a = _load(opts["a"])
        b = _load(opts["b"])

        self.stdout.write(self.style.MIGRATE_HEADING("Scheduler benchmark delta"))
        self.stdout.write(f"  baseline : {opts['a']}")
        self.stdout.write(f"  new      : {opts['b']}")
        self.stdout.write("")

        rows = [
            ("mean_total (s)", a.get("mean_total"), b.get("mean_total")),
            ("stdev_total"   , a.get("stdev_total"), b.get("stdev_total")),
            ("mean_saved"    , a.get("mean_saved"),  b.get("mean_saved")),
        ]
        for name, av, bv in rows:
            delta = None
            if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
                delta = bv - av
            arrow = ""
            if delta is not None:
                if delta < 0: arrow = self.style.SUCCESS(f"  Δ={delta:+.3f}")
                elif delta > 0: arrow = self.style.WARNING(f"  Δ={delta:+.3f}")
                else: arrow = f"  Δ={delta:+.3f}"
            self.stdout.write(f"  {name:<16} {av!r:>12} → {bv!r:<12} {arrow}")

        # Phase timings delta from first run of each report.
        a_phases = (a.get("results") or [{}])[0].get("timings", {})
        b_phases = (b.get("results") or [{}])[0].get("timings", {})
        if a_phases or b_phases:
            self.stdout.write("")
            self.stdout.write("Phase timings (first run):")
            keys = sorted(set(list(a_phases.keys()) + list(b_phases.keys())))
            for k in keys:
                av = a_phases.get(k, 0)
                bv = b_phases.get(k, 0)
                d  = (bv - av) if isinstance(av, (int, float)) and isinstance(bv, (int, float)) else None
                self.stdout.write(
                    f"  {k:<12} {av!r:>8} → {bv!r:<8}"
                    + (f"  Δ={d:+.3f}" if d is not None else "")
                )
