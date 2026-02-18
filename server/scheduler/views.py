from rest_framework import viewsets
from .models import TimeSlot, Timetable, LectureAllocation
from .serializers import (
    TimeSlotSerializer, 
    TimetableSerializer, 
    LectureAllocationSerializer
)


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer

class TimetableViewSet(viewsets.ModelViewSet):
    queryset = Timetable.objects.all()
    serializer_class = TimetableSerializer

class LectureAllocationViewSet(viewsets.ModelViewSet):
    queryset = LectureAllocation.objects.all()
    serializer_class = LectureAllocationSerializer
