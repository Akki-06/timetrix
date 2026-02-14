from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'programs', ProgramViewSet)
router.register(r'terms', AcademicTermViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'student-groups', StudentGroupViewSet)
router.register(r'course-offerings', CourseOfferingViewSet)

urlpatterns = router.urls
