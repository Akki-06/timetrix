# server/ml_pipeline/management/commands/seed_test_data.py
"""
Seeds the database with base data that has no frontend bulk upload:
  - Departments (from Programs Master)
  - Programs (from Programs Master)
  - Buildings + Rooms (from rooms.csv)
  - TimeSlots (from timeslots.csv)

Run:  python manage.py seed_test_data
"""

import csv
import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

log = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent.parent.parent.parent    # server/
DATA = BASE / "ml_pipeline" / "data"
ROOMS_CSV = DATA / "Rooms.csv"
SLOTS_CSV = DATA / "Timeslots.csv"
PROGRAMS_XLSX = DATA / "Programs.xlsx"


class Command(BaseCommand):
    help = "Seed departments, programs, buildings, rooms, and timeslots"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete existing data before seeding (careful!)"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from academics.models import Department, Program
        from infrastructure.models import Building, Room
        from scheduler.models import TimeSlot

        if options["reset"]:
            self.stderr.write(self.style.WARNING(
                "Resetting: TimeSlot, Room, Building, Program, Department..."
            ))
            TimeSlot.objects.all().delete()
            Room.objects.all().delete()
            Building.objects.all().delete()
            Program.objects.all().delete()
            Department.objects.all().delete()

        # ─── 1. Departments & Programs ─────────────────────────────────────
        self.stdout.write(self.style.NOTICE("\n═══ Seeding Departments & Programs ═══"))

        try:
            import openpyxl
            wb = openpyxl.load_workbook(PROGRAMS_XLSX, read_only=True)
            ws = wb.active  # first sheet (Programs)
            rows = list(ws.iter_rows(values_only=True))
            header = rows[0]
            # header: Program, Code, Specialization, Short Form, Department, Years, Semesters
        except Exception as e:
            self.stderr.write(f"Could not read Programs Master: {e}")
            self.stderr.write("Creating minimal default department + program.")
            dept, _ = Department.objects.get_or_create(
                code="CSE", defaults={"name": "Computer Science & Engineering"}
            )
            Program.objects.get_or_create(
                code="BTech CSE",
                defaults={
                    "name": "BTech", "specialization": "CSE",
                    "department": dept, "total_years": 4, "total_semesters": 8,
                },
            )
            rows = []

        DEPT_NAMES = {
            "COA": "Computer Applications",
            "CSE": "Computer Science & Engineering",
            "ECE": "Electronics & Communication Engineering",
            "EE":  "Electrical Engineering",
            "ME":  "Mechanical Engineering",
            "CE":  "Civil Engineering",
        }

        dept_count = 0
        prog_count = 0

        hdr = [str(h).strip() if h else "" for h in header]
        col_idx = {h: i for i, h in enumerate(hdr)}

        for row in rows[1:]:
            if not any(row):
                continue
            name      = str(row[col_idx.get("Program", 0)] or "").strip()
            code      = str(row[col_idx.get("Code", 1)] or "").strip()
            spec      = str(row[col_idx.get("Specialization", 2)] or "").strip()
            short_form = str(row[col_idx.get("Short Form", 3)] or "").strip()
            dept_name_raw = str(row[col_idx.get("Department", 4)] or "").strip()
            years     = int(row[col_idx.get("Years", 5)] or 4)
            sems      = int(row[col_idx.get("Semesters", 6)] or years * 2)
            if not code:
                continue
            dept_name = dept_name_raw or "Unassigned"
            dept_code = dept_name_raw.replace("Department of ", "").replace(" ", "")[:10].upper()

            dept, created = Department.objects.get_or_create(
                name=dept_name,
                defaults={"code": dept_code},
            )
            if created:
                dept_count += 1

            _, created = Program.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "specialization": spec,
                    "short_form": short_form,
                    "department": dept,
                    "total_years": years,
                    "total_semesters": sems,
                },
            )
            if created:
                prog_count += 1

        self.stdout.write(f"  Departments: {dept_count} created")
        self.stdout.write(f"  Programs:    {prog_count} created")

        # ─── 2. Buildings & Rooms ──────────────────────────────────────────
        self.stdout.write(self.style.NOTICE("\n═══ Seeding Buildings & Rooms ═══"))

        building_cache = {}
        room_count = 0

        with open(ROOMS_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                room_id = row["room_id"].strip()
                bldg_name = row["building"].strip()
                floor = int(row["floor"])
                room_type = row["room_type"].strip().upper()
                capacity = int(row["capacity"])
                is_lab = int(row["is_lab"])
                is_shared = int(row.get("is_shared", 1))

                if room_id.lower() in ("rotation", "unknown", ""):
                    continue
                if bldg_name.lower() in ("unknown", "various", ""):
                    continue

                if bldg_name not in building_cache:
                    bcode = bldg_name.replace(" ", "")[:10]
                    bldg, _ = Building.objects.get_or_create(
                        name=bldg_name,
                        defaults={
                            "code": bcode,
                            "floors": max(floor, 3),
                            "is_active": True,
                        },
                    )
                    # Update floors if new room is higher
                    if floor > bldg.floors:
                        bldg.floors = floor
                        bldg.save()
                    building_cache[bldg_name] = bldg
                else:
                    bldg = building_cache[bldg_name]

                _, created = Room.objects.get_or_create(
                    building=bldg,
                    room_number=room_id,
                    defaults={
                        "floor": floor,
                        "room_type": room_type,
                        "capacity": capacity,
                        "is_active": True,
                        "is_shared": bool(is_shared),
                    },
                )
                if created:
                    room_count += 1

        self.stdout.write(f"  Buildings: {len(building_cache)} created/found")
        self.stdout.write(f"  Rooms:     {room_count} created")

        # ─── 3. TimeSlots ──────────────────────────────────────────────────
        self.stdout.write(self.style.NOTICE("\n═══ Seeding TimeSlots ═══"))

        DAY_MAP = {
            "Monday": "MON", "Tuesday": "TUE", "Wednesday": "WED",
            "Thursday": "THU", "Friday": "FRI", "Saturday": "SAT",
        }

        slot_count = 0
        slot_found = 0
        with open(SLOTS_CSV) as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                # CSV has heavy whitespace in both keys and values — strip everything
                row = {k.strip(): v.strip() for k, v in raw_row.items()}

                day_full = row.get("day", "")
                slot_idx = int(row.get("slot_index", 0))
                start = row.get("start_time", "")
                end = row.get("end_time", "")
                is_lunch = int(row.get("is_lunch", 0))

                day_code = DAY_MAP.get(day_full)
                if not day_code:
                    continue

                _, created = TimeSlot.objects.get_or_create(
                    day=day_code,
                    slot_number=slot_idx,
                    defaults={
                        "start_time": start,
                        "end_time": end,
                        "is_lunch": bool(is_lunch),
                    },
                )
                if created:
                    slot_count += 1
                else:
                    slot_found += 1

        self.stdout.write(f"  TimeSlots: {slot_count} created, {slot_found} already existed")

        # ─── Summary ───────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Seed complete. "
            f"{dept_count} depts, {prog_count} programs, "
            f"{room_count} rooms, {slot_count} timeslots."
        ))
