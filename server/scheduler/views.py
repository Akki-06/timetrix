from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.views   import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db              import transaction
from django.db.models        import Max, Q
from django.shortcuts       import get_object_or_404

from academics.models       import AcademicTerm, StudentGroup
from faculty.models         import Faculty
from infrastructure.models  import Room
from .scheduler_engine      import SchedulerEngine

from .models import TimeSlot, Timetable, LectureAllocation, SchedulerConfig, Notification
from .serializers import (
    TimeSlotSerializer,
    TimetableSerializer,
    LectureAllocationSerializer,
    SchedulerConfigSerializer,
    NotificationSerializer,
)


# ----------------------------
# TIME SLOT
# ----------------------------

class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["day", "is_lunch"]


# ----------------------------
# TIMETABLE
# ----------------------------

class TimetableViewSet(viewsets.ModelViewSet):
    queryset = Timetable.objects.select_related("term", "term__program").all()
    serializer_class = TimetableSerializer

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["term", "is_finalized"]
    ordering_fields = ["version", "created_at"]

    def perform_update(self, serializer):
        if serializer.instance.is_finalized:
            raise ValidationError("Cannot modify a finalized timetable.")
        serializer.save()


# ----------------------------
# LECTURE ALLOCATION
# ----------------------------

class LectureAllocationViewSet(viewsets.ModelViewSet):
    queryset = LectureAllocation.objects.select_related(
        "timetable",
        "course_offering",
        "course_offering__course",
        "course_offering__student_group",
        "faculty",
        "room",
        "timeslot"
    )
    serializer_class = LectureAllocationSerializer

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["timetable", "faculty", "room", "timeslot"]

    def perform_create(self, serializer):
        if serializer.validated_data["timetable"].is_finalized:
            raise ValidationError("Cannot add lecture to finalized timetable.")
        serializer.save()

    def perform_update(self, serializer):
        if serializer.instance.timetable.is_finalized:
            raise ValidationError("Cannot modify lecture in finalized timetable.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.timetable.is_finalized:
            raise ValidationError("Cannot delete lecture from finalized timetable.")
        instance.delete()
        
        
class GenerateTimetableView(APIView):
    """
    POST /api/scheduler/generate/

    Accepts either:
        {"term_id": 3}
    OR:
        {"program_id": 1, "semester": 5}   ← preferred from the new UI

    If program_id + semester are given, the AcademicTerm is looked up
    automatically. The scheduler then schedules ALL sections (StudentGroups)
    registered under that term in one run.
    """

    def post(self, request):
        term_id    = request.data.get("term_id")
        program_id = request.data.get("program_id")
        semester   = request.data.get("semester")

        if term_id:
            term = get_object_or_404(AcademicTerm, pk=term_id)
        elif program_id and semester:
            try:
                semester = int(semester)
                program_id = int(program_id)
            except (TypeError, ValueError):
                return Response({"error": "Invalid program_id or semester."}, status=status.HTTP_400_BAD_REQUEST)

            term = AcademicTerm.objects.filter(
                program_id=program_id, semester=semester
            ).first()
            if not term:
                return Response(
                    {"error": "No sections registered for this program/semester. "
                              "Register sections first from the Sections page."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response(
                {"error": "Provide term_id or (program_id + semester)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check that at least one section exists
        section_count = StudentGroup.objects.filter(term=term).count()
        if section_count == 0:
            return Response(
                {"error": "No sections registered under this term. Register sections first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        # Create a new timetable version (auto-increments)
        last_version = (
            Timetable.objects
            .filter(term=term)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        ) or 0
 
        timetable = Timetable.objects.create(
            term    = term,
            version = last_version + 1,
        )
 
        # Auto-create CourseOfferings if none exist for this term.
        # Joins every course for this program+semester with every section.
        # Faculty left blank — scheduler picks from eligibility.
        import logging
        log = logging.getLogger(__name__)
        from academics.models import Course, CourseOffering
        # NOTE: do NOT clear elective_slot_group — admin sets it before
        # clicking Generate so parallel PE electives are grouped correctly.
        existing = CourseOffering.objects.filter(
            student_group__term=term
        ).count()

        if existing == 0:
            courses  = Course.objects.filter(
                program=term.program,
                semester=term.semester,
            ).exclude(course_type__in=["DIS", "INT", "RND"])
            sections = StudentGroup.objects.filter(term=term)
            to_create = [
                CourseOffering(
                    course=course,
                    student_group=section,
                    assigned_faculty=None,
                    weekly_load=0,
                )
                for section in sections
                for course in courses
            ]
            CourseOffering.objects.bulk_create(to_create, ignore_conflicts=True)
            log.info(
                f"Auto-created {len(to_create)} offerings "
                f"({sections.count()} sections × {courses.count()} courses)"
            )

        try:
            engine = SchedulerEngine(timetable_id=timetable.id)
            result = engine.run()
        except Exception as e:
            # If engine crashes entirely, delete the empty timetable
            timetable.delete()
            return Response(
                {"error": f"Scheduler error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
 
        # Always return 201 so the frontend can read the result body.
        # The result["status"] field carries success/partial/failed.
        http_status = status.HTTP_201_CREATED

        # Create in-app notification based on result and user's preferences
        config = SchedulerConfig.get()
        if result["status"] in ("success", "partial") and config.notify_on_generation_complete:
            n_alloc = result.get("allocations", 0)
            n_unsched = len(result.get("unscheduled", []))
            msg = (
                f"Timetable generated: {n_alloc} sessions scheduled"
                + (f", {n_unsched} unscheduled." if result["status"] == "partial" else ".")
            )
            Notification.objects.create(
                message=msg,
                type="success" if result["status"] == "success" else "warning",
            )
        elif result["status"] == "failed" and config.notify_on_failed_generation:
            Notification.objects.create(
                message=f"Timetable generation failed: {result.get('reason', 'Unknown error')}",
                type="error",
            )

        # Auto-publish if configured
        if config.auto_publish_timetable and result["status"] in ("success", "partial"):
            Timetable.objects.filter(pk=timetable.id).update(is_finalized=True)

        # Prune old timetable versions beyond keep_history_versions limit
        keep = config.keep_history_versions
        if keep and keep > 0:
            all_versions = list(
                Timetable.objects.filter(term=term)
                .order_by("-version")
                .values_list("id", flat=True)
            )
            to_delete = all_versions[keep:]
            if to_delete:
                Timetable.objects.filter(id__in=to_delete, is_finalized=False).delete()

        # Attach per-section allocation counts to the result
        sections_info = []
        for grp in StudentGroup.objects.filter(term=term).order_by("name"):
            count = LectureAllocation.objects.filter(
                timetable=timetable,
                student_group=grp,
            ).count()
            sections_info.append({
                "section":  grp.name,
                "strength": grp.strength,
                "allocated": count,
            })
        result["sections"] = sections_info
        result["term_id"]  = term.id
        result["semester"] = term.semester
        result["year"]     = term.year

        return Response(result, status=http_status)


# ----------------------------
# SCHEDULER CONFIG (singleton)
# ----------------------------

class SchedulerConfigView(APIView):
    """
    GET  /api/scheduler/config/  → return current config
    PUT  /api/scheduler/config/  → update config (full replace)
    PATCH /api/scheduler/config/ → partial update
    """

    def get(self, request):
        config = SchedulerConfig.get()
        return Response(SchedulerConfigSerializer(config).data)

    def put(self, request):
        config = SchedulerConfig.get()
        serializer = SchedulerConfigSerializer(config, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request):
        config = SchedulerConfig.get()
        serializer = SchedulerConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ----------------------------
# NOTIFICATIONS
# ----------------------------

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_read", "type"]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    @action(detail=False, methods=["patch"], url_path="mark-all-read")
    def mark_all_read(self, request):
        Notification.objects.filter(is_read=False).update(is_read=True)
        return Response({"marked_read": True})


# ----------------------------
# TIMETABLE SCHEDULE VIEW
# ----------------------------

class TimetableScheduleView(APIView):
    """
    GET /api/scheduler/schedule/

    Returns enriched allocation data for timetable viewing.

    Query params:
      view = section | faculty | room

      section:  student_group_id (required), timetable_id (optional → defaults to latest)
      faculty:  faculty_id (required)
      room:     room_id (required)
    """

    def _latest_tt_ids(self):
        """Return IDs of the latest-version timetable per term."""
        latest = list(
            Timetable.objects.values("term")
            .annotate(max_v=Max("version"))
        )
        if not latest:
            return []
        q = Q()
        for entry in latest:
            q |= Q(term_id=entry["term"], version=entry["max_v"])
        return list(Timetable.objects.filter(q).values_list("id", flat=True))

    def _serialise(self, allocs):
        """Convert queryset of LectureAllocations to enriched dicts."""
        data = []
        for a in allocs:
            co = a.course_offering
            course = co.course
            sg = co.student_group
            term = sg.term
            prog = term.program
            data.append({
                "id":                 a.id,
                "course_code":        course.code,
                "course_name":        course.name,
                "course_type":        course.course_type,
                "faculty_name":       a.faculty.name,
                "faculty_id":         a.faculty.id,
                "room_number":        a.room.room_number,
                "room_type":          a.room.room_type,
                "building_code":      a.room.building.code,
                "room_id":            a.room.id,
                "day":                a.timeslot.day,
                "slot_number":        a.timeslot.slot_number,
                "start_time":         str(a.timeslot.start_time)[:5],
                "end_time":           str(a.timeslot.end_time)[:5],
                "student_group_name": sg.name,
                "student_group_id":   sg.id,
                "is_combined":        "+" in sg.name,
                "program_code":       prog.code,
                "program_name":       prog.name,
                "semester":           term.semester,
            })
        return data

    def get(self, request):
        view = request.query_params.get("view", "section")

        if view == "section":
            sg_id = request.query_params.get("student_group_id")
            tt_id = request.query_params.get("timetable_id")
            if not sg_id:
                return Response(
                    {"error": "student_group_id is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sg = get_object_or_404(StudentGroup, pk=sg_id)

            if tt_id:
                tt = get_object_or_404(Timetable, pk=tt_id)
                if tt.term != sg.term:
                    return Response(
                        {"error": "Timetable does not belong to this section's term."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                tt = Timetable.objects.filter(term=sg.term).order_by("-version").first()

            if not tt:
                return Response({"allocations": [], "timetable": None})

            # Also include combined-group (e.g. A+B) allocations that contain
            # this section, but only for slots that are NOT already occupied by
            # a direct allocation for this section (avoids double-display).
            combined_sgs = StudentGroup.objects.filter(
                term=sg.term, name__contains=sg.name
            ).exclude(pk=sg.pk)
            combined_sgs = [c for c in combined_sgs if sg.name in c.name.split("+")]

            direct_allocs = LectureAllocation.objects.filter(
                timetable=tt, student_group=sg,
            ).select_related(
                "course_offering__course",
                "course_offering__student_group__term__program",
                "faculty", "room__building", "timeslot",
            )
            direct_timeslot_ids = set(direct_allocs.values_list("timeslot_id", flat=True))

            combined_allocs = LectureAllocation.objects.filter(
                timetable=tt,
                student_group_id__in=[c.pk for c in combined_sgs],
            ).exclude(timeslot_id__in=direct_timeslot_ids).select_related(
                "course_offering__course",
                "course_offering__student_group__term__program",
                "faculty", "room__building", "timeslot",
            )

            # Merge into a single list (already select_related above)
            allocs = list(direct_allocs) + list(combined_allocs)
            tt_info = {
                "id": tt.id, "version": tt.version,
                "is_finalized": tt.is_finalized,
            }

        elif view == "faculty":
            fac_id = request.query_params.get("faculty_id")
            if not fac_id:
                return Response(
                    {"error": "faculty_id is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            get_object_or_404(Faculty, pk=fac_id)
            tt_ids = self._latest_tt_ids()
            if not tt_ids:
                return Response({"allocations": [], "timetable": None})
            allocs = LectureAllocation.objects.filter(
                timetable_id__in=tt_ids, faculty_id=fac_id,
            )
            tt_info = None

        elif view == "room":
            room_id = request.query_params.get("room_id")
            if not room_id:
                return Response(
                    {"error": "room_id is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            get_object_or_404(Room, pk=room_id)
            tt_ids = self._latest_tt_ids()
            if not tt_ids:
                return Response({"allocations": [], "timetable": None})
            allocs = LectureAllocation.objects.filter(
                timetable_id__in=tt_ids, room_id=room_id,
            )
            tt_info = None

        else:
            return Response(
                {"error": "Invalid view. Use section, faculty, or room."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Section view already has select_related applied and returns a list;
        # faculty/room views return querysets that still need it.
        if not isinstance(allocs, list):
            allocs = allocs.select_related(
                "course_offering__course",
                "course_offering__student_group__term__program",
                "faculty",
                "room__building",
                "timeslot",
            )

        return Response({
            "allocations": self._serialise(allocs),
            "timetable":   tt_info,
        })