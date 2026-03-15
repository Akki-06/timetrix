from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError
from rest_framework.views   import APIView
from rest_framework.response import Response
from rest_framework         import status
from django.db              import transaction
from django.shortcuts       import get_object_or_404
 
from academics.models       import AcademicTerm
from .scheduler_engine      import SchedulerEngine

from .models import TimeSlot, Timetable, LectureAllocation
from .serializers import (
    TimeSlotSerializer,
    TimetableSerializer,
    LectureAllocationSerializer
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
    queryset = Timetable.objects.select_related("term")
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
 
    Body:
        {
            "term_id": 3
        }
 
    What it does:
        1. Finds the AcademicTerm by term_id
        2. Creates a new Timetable version for that term
        3. Runs SchedulerEngine.run()
        4. Returns result with allocation count, score, unscheduled list
 
    Frontend calls this when admin clicks "Generate Timetable".
    """
 
    def post(self, request):
        term_id = request.data.get("term_id")
        if not term_id:
            return Response(
                {"error": "term_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        term = get_object_or_404(AcademicTerm, pk=term_id)
 
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
 
        http_status = (
            status.HTTP_201_CREATED
            if result["status"] in ("success", "partial")
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
 
        return Response(result, status=http_status)