from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    FacultyViewSet,
    TeacherAvailabilityViewSet,
    FacultySubjectEligibilityViewSet,
    FacultyBulkUploadView,
)

router = DefaultRouter()
router.register(r'faculty', FacultyViewSet)
router.register(r'teacher-availability', TeacherAvailabilityViewSet)
router.register(r'faculty-subject-eligibility', FacultySubjectEligibilityViewSet)

urlpatterns = router.urls + [
    path("faculty/bulk-upload/", FacultyBulkUploadView.as_view(), name="faculty-bulk-upload"),
]
