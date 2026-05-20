"""
Live-streaming variant of the GenerateTimetable endpoint.

POST /api/scheduler/generate-stream/ — returns text/event-stream (SSE).

Each event is a JSON object on a `data: ...\n\n` line. The engine runs in
a worker thread and pushes events into a queue; the view drains the queue
and yields them to the client until a `done` or `error` event arrives.

Event shapes (loosely typed):
    {"type": "phase",   "msg": "...", "phase": "labs",  "elapsed": 1.2}
    {"type": "log",     "msg": "...", "elapsed": 1.2}
    {"type": "assign",  "kind": "PE", "course": "...", "section": "...", ...}
    {"type": "estimate","total_offerings": 47, "estimated_seconds": 25}
    {"type": "done",    "result": { ... full JSON result ... }}
    {"type": "error",   "msg": "..."}
"""
import json
import logging
import queue
import threading
import time

from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from academics.models      import AcademicTerm, StudentGroup, Course, CourseOffering
from scheduler.engine      import SchedulerEngine
from scheduler.engine.progress import ProgressReporter
from scheduler.models      import Timetable, SchedulerConfig, LectureAllocation, Notification

log = logging.getLogger(__name__)


# Empirical baseline: ~0.55s per offering with CP-SAT; ~0.40s without.
# Used to seed the client-side countdown before any real timing arrives.
_BASE_SECONDS_PER_OFFERING = 0.55


def _estimate_seconds(n_offerings: int, n_sections: int) -> float:
    """Conservative estimate so the countdown rarely undershoots."""
    base = max(8.0, n_offerings * _BASE_SECONDS_PER_OFFERING)
    # CP-SAT scales super-linearly with sections × courses; add a small bump
    return round(base + 0.4 * n_sections, 1)


def _run_engine(timetable_id: int, disabled_courses: list,
                q: queue.Queue, result_holder: dict):
    """Worker target: runs the scheduler and pushes events into the queue."""
    reporter = ProgressReporter(q)
    try:
        engine = SchedulerEngine(
            timetable_id     = timetable_id,
            disabled_courses = disabled_courses,
            progress         = reporter,
        )
        result_holder["result"] = engine.run()
    except Exception as exc:
        log.exception("Scheduler thread crashed")
        result_holder["error"] = str(exc)
        reporter.error(f"Engine crashed: {exc}")
    finally:
        # Sentinel — drain loop exits when this lands.
        try:
            q.put_nowait({"type": "_end"})
        except queue.Full:
            pass


@method_decorator(csrf_exempt, name="dispatch")
class GenerateTimetableStreamView(View):
    """SSE endpoint that streams live progress while a timetable is generated.

    Plain Django view (not DRF) so the Accept: text/event-stream header
    from the SPA doesn't trigger DRF's content-negotiation 406.
    """

    def post(self, request):
        # Parse JSON body manually since we're not using DRF's request parser.
        try:
            data = json.loads(request.body.decode("utf-8")) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"error": "Malformed JSON body."}, status=400)

        term_id          = data.get("term_id")
        program_id       = data.get("program_id")
        semester         = data.get("semester")
        disabled_courses = data.get("disabled_courses", [])

        # ── Resolve term (mirrors GenerateTimetableView for client parity) ───
        if term_id:
            term = get_object_or_404(AcademicTerm, pk=term_id)
        elif program_id and semester:
            try:
                semester   = int(semester)
                program_id = int(program_id)
            except (TypeError, ValueError):
                return JsonResponse(
                    {"error": "Invalid program_id or semester."}, status=400,
                )
            term = AcademicTerm.objects.filter(
                program_id=program_id, semester=semester
            ).first()
            if not term:
                return JsonResponse(
                    {"error": "No sections registered for this program/semester."},
                    status=400,
                )
        else:
            return JsonResponse(
                {"error": "Provide term_id or (program_id + semester)."},
                status=400,
            )

        sections = list(StudentGroup.objects.filter(term=term))
        if not sections:
            return JsonResponse(
                {"error": "No sections registered under this term."}, status=400,
            )

        # Bump version (same pattern as the standard endpoint)
        last_version = (
            Timetable.objects.filter(term=term)
            .order_by("-version").values_list("version", flat=True).first()
        ) or 0
        timetable = Timetable.objects.create(term=term, version=last_version + 1)

        # Auto-create offerings if missing
        existing = CourseOffering.objects.filter(student_group__term=term).count()
        if existing == 0:
            courses = Course.objects.filter(
                program=term.program, semester=term.semester
            ).exclude(course_type__in=["DIS", "INT", "RND"])
            to_create = [
                CourseOffering(
                    course=c, student_group=sg,
                    assigned_faculty=None, weekly_load=0,
                )
                for sg in sections for c in courses
            ]
            CourseOffering.objects.bulk_create(to_create, ignore_conflicts=True)

        n_offerings = CourseOffering.objects.filter(student_group__term=term).count()
        est = _estimate_seconds(n_offerings, len(sections))

        # Queue + worker
        q: queue.Queue = queue.Queue(maxsize=2048)
        result_holder: dict = {}
        worker = threading.Thread(
            target=_run_engine,
            args=(timetable.id, disabled_courses, q, result_holder),
            daemon=True,
        )

        def event_stream():
            # Initial estimate frame — UI uses this to seed the countdown.
            yield "data: " + json.dumps({
                "type"              : "estimate",
                "total_offerings"   : n_offerings,
                "total_sections"    : len(sections),
                "estimated_seconds" : est,
                "timetable_id"      : timetable.id,
            }) + "\n\n"

            worker.start()
            last_heartbeat = time.time()

            while True:
                try:
                    ev = q.get(timeout=0.5)
                except queue.Empty:
                    # Heartbeat every 5 s so proxies don't kill the connection.
                    now = time.time()
                    if now - last_heartbeat > 5.0:
                        last_heartbeat = now
                        yield ": heartbeat\n\n"
                    continue

                if ev.get("type") == "_end":
                    break

                yield "data: " + json.dumps(ev) + "\n\n"
                last_heartbeat = time.time()

            # Post-processing: deliver the final result with sections/term info
            # the SPA already expects, then attach notifications + auto-publish.
            err = result_holder.get("error")
            result = result_holder.get("result")
            if err and not result:
                # Engine crashed entirely; roll back the empty timetable row
                # so the history list doesn't show a phantom version.
                timetable.delete()
                yield "data: " + json.dumps(
                    {"type": "error", "msg": err}
                ) + "\n\n"
                return

            config = SchedulerConfig.get()
            if result["status"] in ("success", "partial") and config.notify_on_generation_complete:
                n_alloc   = result.get("allocations", 0)
                n_unsched = len(result.get("unscheduled", []))
                Notification.objects.create(
                    message=(
                        f"Timetable generated: {n_alloc} sessions scheduled"
                        + (f", {n_unsched} unscheduled."
                           if result["status"] == "partial" else ".")
                    ),
                    type="success" if result["status"] == "success" else "warning",
                )
            elif result["status"] == "failed" and config.notify_on_failed_generation:
                Notification.objects.create(
                    message=f"Timetable generation failed: {result.get('reason', 'Unknown error')}",
                    type="error",
                )

            if config.auto_publish_timetable and result["status"] in ("success", "partial"):
                Timetable.objects.filter(pk=timetable.id).update(is_finalized=True)

            keep = config.keep_history_versions
            if keep and keep > 0:
                all_versions = list(
                    Timetable.objects.filter(term=term)
                    .order_by("-version").values_list("id", flat=True)
                )
                to_delete = all_versions[keep:]
                if to_delete:
                    Timetable.objects.filter(
                        id__in=to_delete, is_finalized=False
                    ).delete()

            # Per-section breakdown — matches non-stream endpoint
            sections_info = []
            for grp in StudentGroup.objects.filter(term=term).order_by("name"):
                count = LectureAllocation.objects.filter(
                    timetable=timetable, student_group=grp,
                ).count()
                sections_info.append({
                    "section"  : grp.name,
                    "strength" : grp.strength,
                    "allocated": count,
                })
            result["sections"] = sections_info
            result["term_id"]  = term.id
            result["semester"] = term.semester
            result["year"]     = term.year

            yield "data: " + json.dumps(
                {"type": "result", "result": result}
            ) + "\n\n"
            yield "data: " + json.dumps({"type": "complete"}) + "\n\n"

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream"
        )
        response["Cache-Control"]    = "no-cache"
        response["X-Accel-Buffering"] = "no"   # disable nginx buffering
        return response
