import math
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
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
    queryset = StudentGroup.objects.select_related("term", "term__program", "term__program__department")
    serializer_class = StudentGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["term", "term__program", "term__semester"]
    search_fields = ["name", "description"]

    @action(detail=False, methods=["post"], url_path="quick-create")
    def quick_create(self, request):
        """
        Single-step creation: admin provides program + semester + section + strength.
        Automatically finds or creates the AcademicTerm, then creates the StudentGroup.
        """
        program_id = request.data.get("program")
        semester   = request.data.get("semester")
        section    = request.data.get("section", "").strip()
        strength   = request.data.get("strength")
        description = request.data.get("description", "")

        if not all([program_id, semester, section, strength]):
            return Response(
                {"error": "program, semester, section, and strength are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            program_id = int(program_id)
            semester   = int(semester)
            strength   = int(strength)
        except (ValueError, TypeError):
            return Response({"error": "Invalid numeric values."}, status=status.HTTP_400_BAD_REQUEST)

        if strength <= 0:
            return Response({"error": "Strength must be > 0."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate program exists (404 if not)
        program = get_object_or_404(Program, pk=program_id)

        # Derive academic year from semester (sem 1-2 → year 1, sem 3-4 → year 2 …)
        year = math.ceil(semester / 2)

        # Auto-create AcademicTerm if it doesn't exist yet
        term, _ = AcademicTerm.objects.get_or_create(
            program_id=program.id,
            semester=semester,
            defaults={"year": year},
        )

        # Create section (or update strength if it already exists)
        group, created = StudentGroup.objects.get_or_create(
            term=term,
            name=section,
            defaults={"strength": strength, "description": description},
        )
        if not created:
            group.strength = strength
            if description:
                group.description = description
            group.save()

        data = StudentGroupSerializer(group).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


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