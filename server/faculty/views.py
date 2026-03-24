import logging

from django.db import transaction
from rest_framework import viewsets, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from django_filters.rest_framework import DjangoFilterBackend

from .models import Faculty, TeacherAvailability, FacultySubjectEligibility
from .serializers import (
    FacultySerializer,
    TeacherAvailabilitySerializer,
    FacultySubjectEligibilitySerializer
)

log = logging.getLogger(__name__)


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


# ----------------------------
# FACULTY BULK UPLOAD
# ----------------------------

ROLE_MAP = {
    "dean": "DEAN",
    "hod": "HOD",
    "head of department": "HOD",
    "pro vice chancellor": "PVC",
    "pvc": "PVC",
    "associate professor": "REGULAR",
    "professor": "REGULAR",
    "regular": "REGULAR",
    "assistant professor": "REGULAR",
    "visiting": "VISITING",
    "visiting faculty": "VISITING",
}


class FacultyBulkUploadView(APIView):
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

        required = {"name", "employee_id"}
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
                    name = str(row[col["name"]] or "").strip()
                    emp_id = str(row[col["employee_id"]] or "").strip()

                    if not name or not emp_id:
                        errors.append(f"Row {row_num}: name or employee_id is empty, skipped.")
                        continue

                    role_raw = str(row[col["role"]] or "REGULAR").strip().lower() if "role" in col else "regular"
                    role = ROLE_MAP.get(role_raw, "REGULAR")

                    max_weekly = int(row[col["max_weekly_load"]]) if "max_weekly_load" in col and row[col["max_weekly_load"]] else 18
                    max_daily = int(row[col["max_lectures_per_day"]]) if "max_lectures_per_day" in col and row[col["max_lectures_per_day"]] else 4
                    max_consec = int(row[col["max_consecutive_lectures"]]) if "max_consecutive_lectures" in col and row[col["max_consecutive_lectures"]] else 2

                    obj, was_created = Faculty.objects.get_or_create(
                        employee_id=emp_id,
                        defaults={
                            "name": name,
                            "role": role,
                            "max_weekly_load": max_weekly,
                            "max_lectures_per_day": max_daily,
                            "max_consecutive_lectures": max_consec,
                        },
                    )

                    if was_created:
                        created += 1
                    else:
                        obj.name = name
                        obj.role = role
                        obj.max_weekly_load = max_weekly
                        obj.max_lectures_per_day = max_daily
                        obj.max_consecutive_lectures = max_consec
                        obj.save()
                        updated += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {e}")

        return Response(
            {"created": created, "updated": updated, "errors": errors},
            status=status.HTTP_200_OK,
        )