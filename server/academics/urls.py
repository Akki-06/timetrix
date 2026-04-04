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
    ProgramBulkUploadView,
    TemplateDownloadView,
)

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'programs', ProgramViewSet)
router.register(r'terms', AcademicTermViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'student-groups', StudentGroupViewSet)
router.register(r'course-offerings', CourseOfferingViewSet)

urlpatterns = [
    path("courses/bulk-upload/", CourseBulkUploadView.as_view(), name="course-bulk-upload"),
    path("programs/bulk-upload/", ProgramBulkUploadView.as_view(), name="program-bulk-upload"),
    path("templates/download/", TemplateDownloadView.as_view(), name="template-download"),
] + router.urls
