"""
Live progress reporter for the scheduler engine.

Pushes structured events onto a thread-safe queue so the SSE endpoint can
stream them to the admin UI in real time. The engine calls `emit(...)`;
the queue is drained by the HTTP layer.

Events are dict-shaped:
    {"type": "phase"|"log"|"assign"|"progress"|"done", "msg": str, ...}

A No-op reporter is used when streaming is disabled so engine code stays
identical regardless of caller.
"""
import queue
import time
from typing import Optional


class ProgressReporter:
    """Thread-safe sink for live events. Wrap None when streaming is off."""

    def __init__(self, q: Optional[queue.Queue] = None):
        self._q = q
        self._t0 = time.perf_counter()

    def _elapsed(self) -> float:
        return round(time.perf_counter() - self._t0, 2)

    def emit(self, event_type: str, message: str = "", **extra) -> None:
        if self._q is None:
            return
        payload = {
            "type"    : event_type,
            "msg"     : message,
            "elapsed" : self._elapsed(),
            **extra,
        }
        try:
            self._q.put_nowait(payload)
        except queue.Full:
            pass

    # ── Convenience helpers — kept terse so engine call sites stay readable ──

    def phase(self, name: str, msg: str = "") -> None:
        self.emit("phase", msg or name, phase=name)

    def log(self, msg: str, **extra) -> None:
        self.emit("log", msg, **extra)

    def assign(self, kind: str, course: str, section: str,
               faculty: str = "", room: str = "",
               day: str = "", slot: int = 0) -> None:
        """Per-allocation event so the terminal UI can stream 'PE ✓ ...' lines."""
        self.emit(
            "assign",
            f"{kind} ✓ {course} ({section})",
            kind=kind, course=course, section=section,
            faculty=faculty, room=room, day=day, slot=slot,
        )

    def progress(self, done: int, total: int, label: str = "") -> None:
        self.emit("progress", label, done=done, total=total,
                  pct=round(100.0 * done / max(total, 1), 1))

    def done(self, result: dict) -> None:
        self.emit("done", "Generation complete", result=result)

    def error(self, msg: str) -> None:
        self.emit("error", msg)
