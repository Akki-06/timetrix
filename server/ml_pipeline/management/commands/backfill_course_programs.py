# server/ml_pipeline/management/commands/backfill_course_programs.py
"""
Backfills missing program/semester on Course records by reading
Courses.xlsx and linking each course to its program.

Run after courses and programs are uploaded:
    python manage.py backfill_course_programs
"""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

DATA = Path(__file__).resolve().parent.parent.parent.parent / "ml_pipeline" / "data"
COURSES_XLSX = DATA / "Courses.xlsx"


class Command(BaseCommand):
    help = "Backfill program/semester FK on Course records from the Courses Excel"

    @transaction.atomic
    def handle(self, *args, **options):
        import openpyxl
        from academics.models import Course, Program

        if not COURSES_XLSX.exists():
            self.stderr.write(self.style.ERROR(f"File not found: {COURSES_XLSX}"))
            return

        wb = openpyxl.load_workbook(COURSES_XLSX, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            self.stderr.write(self.style.ERROR("Excel file has no data rows."))
            return

        header = [str(h or "").strip().lower().replace(" ", "_") for h in rows[0]]
        col = {name: idx for idx, name in enumerate(header)}

        if "code" not in col:
            self.stderr.write(self.style.ERROR("Missing 'code' column in Excel."))
            return

        # Build program lookup
        program_map = {p.code.strip().lower(): p for p in Program.objects.all()}

        # Build a lookup map for DB courses by code (exact) and by stripped code
        # E.g. Excel has "24COA274_BCA", DB has "24COA274"
        course_by_code = {c.code: c for c in Course.objects.all()}

        updated = 0
        skipped_no_prog = 0
        skipped_no_course = 0
        already_set = 0

        for row_num, row in enumerate(rows[1:], start=2):
            excel_code = str(row[col["code"]] or "").strip()
            if not excel_code:
                continue

            # Resolve program
            program = None
            if "program_code" in col and row[col["program_code"]]:
                prog_code = str(row[col["program_code"]]).strip()
                program = program_map.get(prog_code.lower())
                if not program:
                    skipped_no_prog += 1
                    continue
            else:
                # Try to infer program from code suffix e.g. "24COA274_BCA" → "BCA"
                if "_" in excel_code:
                    suffix = excel_code.rsplit("_", 1)[-1]
                    program = program_map.get(suffix.lower())

            # Resolve semester
            semester = None
            if "semester" in col and row[col["semester"]]:
                try:
                    semester = int(row[col["semester"]])
                except (ValueError, TypeError):
                    pass

            # Find course in DB: try exact code first, then code with suffix stripped
            course = course_by_code.get(excel_code)
            if course is None and "_" in excel_code:
                # Strip program suffix: "24COA274_BCA" → "24COA274"
                stripped = excel_code.rsplit("_", 1)[0]
                course = course_by_code.get(stripped)

            if course is None:
                skipped_no_course += 1
                continue

            changed = False
            if program and course.program_id != program.id:
                course.program = program
                changed = True
            elif course.program_id:
                already_set += 1

            if semester and course.semester != semester:
                course.semester = semester
                changed = True

            if changed:
                course.save(update_fields=["program", "semester"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nBackfill done: {updated} courses updated, "
            f"{already_set} already had program set."
        ))
        if skipped_no_prog:
            self.stdout.write(self.style.WARNING(
                f"  {skipped_no_prog} rows skipped (program code not found in DB)"
            ))
        if skipped_no_course:
            self.stdout.write(self.style.WARNING(
                f"  {skipped_no_course} rows skipped (course code not in DB — upload courses first)"
            ))
