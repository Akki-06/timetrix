from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    FacultyViewSet,
    TeacherAvailabilityViewSet,
    FacultySubjectEligibilityViewSet,
    FacultyBulkUploadView,
    EligibilityBulkUploadView,
    FacultyWorkloadView,
    FacultyProgramExclusionViewSet,
    FacultySemesterExclusionViewSet,
)

router = DefaultRouter()
router.register(r'faculty', FacultyViewSet)
router.register(r'teacher-availability', TeacherAvailabilityViewSet)
router.register(r'faculty-subject-eligibility', FacultySubjectEligibilityViewSet)
router.register(r'program-exclusions', FacultyProgramExclusionViewSet)
router.register(r'semester-exclusions', FacultySemesterExclusionViewSet)

urlpatterns = [
    path("faculty/bulk-upload/", FacultyBulkUploadView.as_view(), name="faculty-bulk-upload"),
    path("eligibility/bulk-upload/", EligibilityBulkUploadView.as_view(), name="eligibility-bulk-upload"),
    path("faculty/workload/", FacultyWorkloadView.as_view(), name="faculty-workload"),
] + router.urls
