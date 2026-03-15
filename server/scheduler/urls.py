from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    TimeSlotViewSet,
    TimetableViewSet,
    LectureAllocationViewSet,
    GenerateTimetableView,        
)

router = DefaultRouter()
router.register(r"timeslots",   TimeSlotViewSet)
router.register(r"timetables",  TimetableViewSet)
router.register(r"allocations", LectureAllocationViewSet)

urlpatterns = router.urls + [
    path("generate/", GenerateTimetableView.as_view(), name="generate-timetable"),
]