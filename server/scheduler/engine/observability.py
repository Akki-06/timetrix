"""
Observability: rejection logging and run timing (improvement #10).

RejectionLog records why each candidate was rejected so failures can be
explained to the admin. RunTimer records wall-clock time per pipeline phase
so regressions are easy to spot.
"""
import logging
import time
from collections import Counter, defaultdict
from contextlib import contextmanager

log = logging.getLogger(__name__)


class RejectionLog:
    """Per-offering reason bucket. Admin UI can render top N reasons."""

    def __init__(self):
        self._by_offering: dict[int, Counter] = defaultdict(Counter)
        self._global: Counter = Counter()

    def record(self, offering_id, reason: str):
        if not reason:
            return
        norm = self._normalize(reason)
        self._by_offering[offering_id][norm] += 1
        self._global[norm] += 1

    @staticmethod
    def _normalize(reason: str) -> str:
        # Collapse e.g. "faculty 17 busy at MON S3" -> "faculty busy"
        tokens = []
        for tok in reason.split():
            if tok.isdigit():
                continue
            tokens.append(tok)
        norm = " ".join(tokens)
        if "busy" in norm:
            if "faculty" in norm: return "faculty busy"
            if "room"    in norm: return "room busy"
            if "group"   in norm: return "group busy"
        if "weekly limit"  in norm: return "faculty at weekly cap"
        if "daily limit"   in norm: return "faculty at daily cap"
        if "consecutive"   in norm: return "would exceed max consecutive"
        if "capacity"      in norm: return "room capacity insufficient"
        if "off day"       in norm or "off-day" in norm: return "off-day exclusion"
        return norm[:64]

    def top(self, offering_id, n: int = 3) -> list[tuple[str, int]]:
        return self._by_offering.get(offering_id, Counter()).most_common(n)

    def summary(self, n: int = 5) -> list[tuple[str, int]]:
        return self._global.most_common(n)

    def to_dict(self, n: int = 3) -> dict:
        return {oid: c.most_common(n) for oid, c in self._by_offering.items()}


class RunTimer:
    """Wall-clock timer for named phases. Usage: with timer.phase('load'): ..."""

    def __init__(self):
        self._phases: dict[str, float] = {}
        self._t0 = time.perf_counter()

    @contextmanager
    def phase(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self._phases[name] = self._phases.get(name, 0.0) + elapsed
            log.info(f"  [timer] {name}: {elapsed:.3f}s")

    def total(self) -> float:
        return time.perf_counter() - self._t0

    def as_dict(self) -> dict:
        out = dict(self._phases)
        out["total"] = round(self.total(), 4)
        return {k: round(v, 4) for k, v in out.items()}
