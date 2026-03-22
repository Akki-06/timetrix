from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    TimeSlotViewSet,
    TimetableViewSet,
    LectureAllocationViewSet,
    GenerateTimetableView,
    SchedulerConfigView,
    NotificationViewSet,
    TimetableScheduleView,
)

router = DefaultRouter()
router.register(r"timeslots",     TimeSlotViewSet)
router.register(r"timetables",   TimetableViewSet)
router.register(r"allocations",  LectureAllocationViewSet)
router.register(r"notifications", NotificationViewSet)

urlpatterns = router.urls + [
    path("generate/", GenerateTimetableView.as_view(), name="generate-timetable"),
    path("config/",   SchedulerConfigView.as_view(),   name="scheduler-config"),
    path("schedule/", TimetableScheduleView.as_view(), name="timetable-schedule"),
]