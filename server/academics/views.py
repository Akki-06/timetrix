import math
import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

log = logging.getLogger(__name__)
from .models import (
    Department,
    Program,
    AcademicTerm,
    Course,
    CourseType,
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
    queryset = Course.objects.select_related("program").all()
    serializer_class = CourseSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["course_type", "program", "semester"]
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

    @action(detail=True, methods=["post"], url_path="auto-assign-courses")
    def auto_assign_courses(self, request, pk=None):
        """
        Auto-create CourseOfferings for all courses that match this
        section's program + semester.

        POST /api/academics/student-groups/{id}/auto-assign-courses/

        Optional body: {"overwrite": true} to delete existing offerings first.
        """
        group = self.get_object()
        term = group.term
        program = term.program
        semester = term.semester

        overwrite = request.data.get("overwrite", False)

        # Non-schedulable types excluded
        NON_SCHED = {"DIS", "INT", "RND"}

        courses = Course.objects.filter(
            program=program,
            semester=semester,
        ).exclude(course_type__in=NON_SCHED)

        if not courses.exists():
            return Response(
                {"error": f"No schedulable courses found for {program.code} Sem {semester}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if overwrite:
            CourseOffering.objects.filter(student_group=group).delete()

        created_count = 0
        already_existed = 0
        course_codes = []

        for course in courses:
            _, was_created = CourseOffering.objects.get_or_create(
                course=course,
                student_group=group,
                defaults={"weekly_load": course.min_weekly_lectures},
            )
            if was_created:
                created_count += 1
            else:
                already_existed += 1
            course_codes.append(course.code)

        return Response({
            "created": created_count,
            "already_existed": already_existed,
            "courses": course_codes,
        })


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


# ----------------------------
# COURSE BULK UPLOAD
# ----------------------------

# Map full names → short codes for course_type
_COURSE_TYPE_MAP = {
    "program core": "PC", "pc": "PC",
    "program elective": "PE", "pe": "PE",
    "open elective": "OE", "oe": "OE",
    "basic sciences course": "BSC", "bsc": "BSC",
    "engineering sciences course": "ESC", "esc": "ESC",
    "humanities": "HUM", "hum": "HUM",
    "life skills": "LS", "ls": "LS",
    "value added module": "VAM", "vam": "VAM",
    "ability enhancement course": "AEC", "aec": "AEC",
    "practical (lab)": "PR", "practical": "PR", "lab": "PR", "pr": "PR",
    "project": "PRJ", "prj": "PRJ",
    "dissertation": "DIS", "dis": "DIS",
    "internship": "INT", "int": "INT",
    "research": "RND", "rnd": "RND",
}

VALID_COURSE_TYPES = {c[0] for c in CourseType.choices}


class CourseBulkUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file provided. Upload an .xlsx file with field name 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not file.name.endswith(".xlsx"):
            return Response(
                {"error": "Only .xlsx files are supported."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            import openpyxl
        except ImportError:
            return Response(
                {"error": "openpyxl is not installed. Run: pip install openpyxl"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            wb = openpyxl.load_workbook(file, read_only=True)
            ws = wb.active
        except Exception as e:
            return Response(
                {"error": f"Could not read Excel file: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return Response(
                {"error": "File must have a header row and at least one data row."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        header = [str(h).strip().lower().replace(" ", "_") if h else "" for h in rows[0]]

        required = {"code", "name", "credits", "course_type"}
        if not required.issubset(set(header)):
            return Response(
                {"error": f"Missing required columns: {required - set(header)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        col = {name: idx for idx, name in enumerate(header)}
        created = 0
        updated = 0
        errors = []

        with transaction.atomic():
            for row_num, row in enumerate(rows[1:], start=2):
                try:
                    code = str(row[col["code"]] or "").strip()
                    name = str(row[col["name"]] or "").strip()
                    credits_val = int(row[col["credits"]] or 3)

                    if not code or not name:
                        errors.append(f"Row {row_num}: code or name is empty, skipped.")
                        continue

                    # Resolve course_type
                    ct_raw = str(row[col["course_type"]] or "PC").strip()
                    ct = _COURSE_TYPE_MAP.get(ct_raw.lower(), ct_raw.upper())
                    if ct not in VALID_COURSE_TYPES:
                        errors.append(f"Row {row_num}: unknown course_type '{ct_raw}', skipped.")
                        continue

                    # Resolve program (optional)
                    program = None
                    semester = None
                    if "program_code" in col and row[col["program_code"]]:
                        prog_code = str(row[col["program_code"]]).strip()
                        try:
                            program = Program.objects.get(code__iexact=prog_code)
                        except Program.DoesNotExist:
                            errors.append(f"Row {row_num}: program '{prog_code}' not found, skipped.")
                            continue
                    if "semester" in col and row[col["semester"]]:
                        semester = int(row[col["semester"]])

                    obj, was_created = Course.objects.get_or_create(
                        code=code,
                        defaults={
                            "name": name,
                            "credits": credits_val,
                            "course_type": ct,
                            "program": program,
                            "semester": semester,
                        },
                    )

                    if was_created:
                        created += 1
                    else:
                        obj.name = name
                        obj.credits = credits_val
                        obj.course_type = ct
                        if program:
                            obj.program = program
                        if semester:
                            obj.semester = semester
                        obj.save()
                        updated += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {e}")

        return Response(
            {"created": created, "updated": updated, "errors": errors},
            status=status.HTTP_200_OK,
        )