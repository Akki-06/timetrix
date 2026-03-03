from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    Department,
    Program,
    AcademicTerm,
    Course,
    StudentGroup,
    CourseOffering
)
from .serializers import (
    DepartmentSerializer,
    ProgramSerializer,
    AcademicTermSerializer,
    CourseSerializer,
    StudentGroupSerializer,
    CourseOfferingSerializer
)


# ----------------------------
# DEPARTMENT
# ----------------------------

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "code"]


# ----------------------------
# PROGRAM
# ----------------------------

class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.select_related("department")
    serializer_class = ProgramSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["department"]
    search_fields = ["name", "code"]


# ----------------------------
# ACADEMIC TERM
# ----------------------------

class AcademicTermViewSet(viewsets.ModelViewSet):
    queryset = AcademicTerm.objects.select_related("program")
    serializer_class = AcademicTermSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["program", "year", "semester"]


# ----------------------------
# COURSE
# ----------------------------

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["course_type"]
    search_fields = ["name", "code"]


# ----------------------------
# STUDENT GROUP
# ----------------------------

class StudentGroupViewSet(viewsets.ModelViewSet):
    queryset = StudentGroup.objects.select_related("term")
    serializer_class = StudentGroupSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["term"]


# ----------------------------
# COURSE OFFERING
# ----------------------------

class CourseOfferingViewSet(viewsets.ModelViewSet):
    queryset = CourseOffering.objects.select_related(
        "course",
        "student_group",
        "assigned_faculty"
    )
    serializer_class = CourseOfferingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["course", "student_group", "assigned_faculty"]