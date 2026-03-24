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

    @action(detail=False, methods=["post"], url_path="quick-assign")
    def quick_assign(self, request):
        """
        Assign a course to a section by human-readable codes.
        Accepts: course_code, program_code, semester, section,
                 assigned_faculty_employee_id (optional), weekly_load (optional).
        Creates the CourseOffering if it doesn't exist, updates it if it does.
        """
        from faculty.models import Faculty as FacultyModel

        course_code = str(request.data.get("course_code", "")).strip().upper()
        program_code = str(request.data.get("program_code", "")).strip()
        section = str(request.data.get("section", "")).strip().upper()
        faculty_emp_id = str(request.data.get("assigned_faculty_employee_id", "")).strip()

        try:
            semester = int(request.data.get("semester", 0))
            weekly_load = int(request.data.get("weekly_load", 0))
        except (ValueError, TypeError):
            return Response(
                {"error": "semester and weekly_load must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not all([course_code, program_code, semester, section]):
            return Response(
                {"error": "course_code, program_code, semester, and section are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            course = Course.objects.get(code=course_code)
        except Course.DoesNotExist:
            return Response(
                {"error": f"Course '{course_code}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            program = Program.objects.get(code=program_code)
        except Program.DoesNotExist:
            return Response(
                {"error": f"Program '{program_code}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        term = AcademicTerm.objects.filter(
            program=program, semester=semester
        ).first()
        if not term:
            return Response(
                {"error": (
                    f"No term found for program '{program_code}' semester {semester}. "
                    "Register the section first from the Sections page."
                )},
                status=status.HTTP_404_NOT_FOUND,
            )

        student_group = StudentGroup.objects.filter(
            term=term, name=section
        ).first()
        if not student_group:
            return Response(
                {"error": (
                    f"Section '{section}' not found for {program_code} Sem {semester}. "
                    "Register the section first from the Sections page."
                )},
                status=status.HTTP_404_NOT_FOUND,
            )

        assigned_faculty = None
        if faculty_emp_id:
            assigned_faculty = FacultyModel.objects.filter(
                employee_id=faculty_emp_id
            ).first()
            if not assigned_faculty:
                return Response(
                    {"error": f"Faculty with employee_id '{faculty_emp_id}' not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        offering, created = CourseOffering.objects.get_or_create(
            course=course,
            student_group=student_group,
            defaults={
                "assigned_faculty": assigned_faculty,
                "weekly_load": weekly_load,
            },
        )
        if not created:
            if assigned_faculty is not None:
                offering.assigned_faculty = assigned_faculty
            if weekly_load:
                offering.weekly_load = weekly_load
            offering.save()

        return Response(
            CourseOfferingSerializer(offering).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )