from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'faculty', FacultyViewSet)
router.register(r'teacher-availaiblity', TeacherAvailabilityViewSet)
router.register(r'faculty-sub-eligiblity', FacultySubjectEligibilityViewSet)

urlpatterns = router.urls