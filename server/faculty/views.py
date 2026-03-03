from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Faculty, TeacherAvailability, FacultySubjectEligibility
from .serializers import (
    FacultySerializer,
    TeacherAvailabilitySerializer,
    FacultySubjectEligibilitySerializer
)


# ----------------------------
# FACULTY
# ----------------------------

class FacultyViewSet(viewsets.ModelViewSet):
    queryset = Faculty.objects.all()
    serializer_class = FacultySerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["role", "is_active"]
    search_fields = ["name", "employee_id"]
    ordering_fields = ["name", "employee_id", "role"]


# ----------------------------
# TEACHER AVAILABILITY
# ----------------------------

class TeacherAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = TeacherAvailability.objects.select_related("faculty")
    serializer_class = TeacherAvailabilitySerializer

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["faculty", "day"]


# ----------------------------
# FACULTY SUBJECT ELIGIBILITY
# ----------------------------

class FacultySubjectEligibilityViewSet(viewsets.ModelViewSet):
    queryset = FacultySubjectEligibility.objects.select_related(
        "faculty",
        "course"
    )
    serializer_class = FacultySubjectEligibilitySerializer

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["faculty", "course"]