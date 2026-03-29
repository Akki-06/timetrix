from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet,
    ProgramViewSet,
    AcademicTermViewSet,
    CourseViewSet,
    StudentGroupViewSet,
    CourseOfferingViewSet,
    CourseBulkUploadView,
)

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'programs', ProgramViewSet)
router.register(r'terms', AcademicTermViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'student-groups', StudentGroupViewSet)
router.register(r'course-offerings', CourseOfferingViewSet)

urlpatterns = router.urls + [
    path("courses/bulk-upload/", CourseBulkUploadView.as_view(), name="course-bulk-upload"),
]
