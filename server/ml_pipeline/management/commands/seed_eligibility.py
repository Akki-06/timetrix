# server/ml_pipeline/management/commands/seed_eligibility.py
"""
Parses the Faculty Master Excel "Subject Eligibility" column and creates
FacultySubjectEligibility records linking faculty to courses.

Format: "Advanced Web Technology Lab:L; Computer Graphics:T; DBMS:T+L"
  T   = theory only
  L   = lab only
  T+L = both theory and lab

Run AFTER faculty and courses are uploaded:
    python manage.py seed_eligibility
"""

import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

log = logging.getLogger(__name__)

DATA = Path(__file__).resolve().parent.parent.parent.parent / "ml_pipeline" / "data"
FACULTY_XLSX = DATA / "TIMETRIX_Faculty_Master_Data.xlsx"


class Command(BaseCommand):
    help = "Create FacultySubjectEligibility records from Faculty Master Excel"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete all existing eligibility records first",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from faculty.models import Faculty, FacultySubjectEligibility
        from academics.models import Course

        if options["reset"]:
            count = FacultySubjectEligibility.objects.all().delete()[0]
            self.stderr.write(self.style.WARNING(
                f"Deleted {count} existing eligibility records."
            ))

        import openpyxl
        wb = openpyxl.load_workbook(FACULTY_XLSX, read_only=True)
        ws = wb["Faculty Master"]
        rows = list(ws.iter_rows(values_only=True))

        # Find real header row (has "Full Name" and "Subject Eligibility")
        header_idx = None
        for i, row in enumerate(rows):
            row_str = " ".join(str(c or "") for c in row).lower()
            if "full name" in row_str and "eligibility" in row_str:
                header_idx = i
                break

        if header_idx is None:
            self.stderr.write(self.style.ERROR(
                "Could not find header row in Faculty Master."
            ))
            return

        header = [str(c or "").strip().lower() for c in rows[header_idx]]

        # Find column indices
        name_col = None
        elig_col = None
        for i, h in enumerate(header):
            if "full name" in h:
                name_col = i
            if "subject eligibility" in h or "eligibility" in h:
                elig_col = i

        if name_col is None or elig_col is None:
            self.stderr.write(self.style.ERROR(
                f"Missing columns. Found: {header}"
            ))
            return

        # Build course lookup: name (lowered) → Course object
        # Also try partial matches since Excel names may differ slightly
        course_by_name = {}
        for c in Course.objects.all():
            course_by_name[c.name.strip().lower()] = c

        # Build faculty lookup: name → Faculty object
        fac_by_name = {}
        for f in Faculty.objects.filter(is_active=True):
            fac_by_name[f.name.strip().lower()] = f

        created = 0
        skipped_no_fac = 0
        skipped_no_course = 0
        already_existed = 0

        for row in rows[header_idx + 1:]:
            fac_name = str(row[name_col] or "").strip()
            elig_str = str(row[elig_col] or "").strip()

            if not fac_name or not elig_str:
                continue

            fac = fac_by_name.get(fac_name.lower())
            if not fac:
                skipped_no_fac += 1
                continue

            # Parse eligibility: "DBMS:T+L; SE:T; Web Lab:L"
            entries = [e.strip() for e in elig_str.split(";") if e.strip()]
            for entry in entries:
                if ":" not in entry:
                    # Try just the subject name with no type marker
                    subj_name = entry.strip()
                    type_marker = "T"
                else:
                    parts = entry.rsplit(":", 1)
                    subj_name = parts[0].strip()
                    type_marker = parts[1].strip().upper() if len(parts) > 1 else "T"

                if not subj_name:
                    continue

                # Find course by name (try exact first, then contains)
                course = course_by_name.get(subj_name.lower())
                if not course:
                    # Try partial match — "DBMS" might match
                    # "Database Management Systems"
                    candidates = [
                        c for name, c in course_by_name.items()
                        if subj_name.lower() in name
                    ]
                    if len(candidates) == 1:
                        course = candidates[0]
                    elif len(candidates) > 1:
                        # Multiple matches — take exact substring matches
                        # or just pick the first one
                        course = candidates[0]

                if not course:
                    skipped_no_course += 1
                    continue

                # Priority: T+L > T > L
                priority = 3 if "T" in type_marker and "L" in type_marker else \
                           2 if "T" in type_marker else 1

                _, was_created = FacultySubjectEligibility.objects.get_or_create(
                    faculty=fac,
                    course=course,
                    defaults={"priority_weight": priority},
                )
                if was_created:
                    created += 1
                else:
                    already_existed += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Eligibility seeded: {created} created, "
            f"{already_existed} already existed."
        ))
        if skipped_no_fac:
            self.stdout.write(self.style.WARNING(
                f"  {skipped_no_fac} entries skipped (faculty not found in DB — "
                f"upload faculty first)"
            ))
        if skipped_no_course:
            self.stdout.write(self.style.WARNING(
                f"  {skipped_no_course} entries skipped (course not found in DB — "
                f"upload courses first)"
            ))
