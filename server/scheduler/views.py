from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError

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