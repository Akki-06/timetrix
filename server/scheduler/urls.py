from rest_framework.routers import DefaultRouter
from .views import (
    TimeSlotViewSet,
    TimetableViewSet,
    LectureAllocationViewSet
)

router = DefaultRouter()
router.register(r'timeslots', TimeSlotViewSet)
router.register(r'timetables', TimetableViewSet)
router.register(r'allocations', LectureAllocationViewSet)

urlpatterns = router.urls
