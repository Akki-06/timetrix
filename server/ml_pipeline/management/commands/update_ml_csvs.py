import csv
import pandas as pd
from pathlib import Path
from django.core.management.base import BaseCommand
from academics.models import CourseOffering, StudentGroup, Program
from faculty.models import Faculty
from infrastructure.models import Room
from scheduler.models import TimeSlot

class Command(BaseCommand):
    help = "Update ML pipeline CSVs from current database state"

    def handle(self, *args, **options):
        DATA_DIR = Path('ml_pipeline/data')
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # 1. Update faculty_metadata.csv
        faculties = Faculty.objects.all()
        fac_data = []
        for f in faculties:
            fac_data.append({
                'faculty_name': f.name,
                'designation': f.get_role_display(),
                'max_hours_per_week': f.max_weekly_load,
                'teaches_theory': 1,
                'teaches_lab': 1,
                'num_unique_courses': 3,
                'num_programs_taught': 2,
                'employment_type': 'Full Time' if f.role != 'VISITING' else 'Visiting',
                'is_hod': 1 if f.role == 'HOD' else 0,
                'is_dean': 1 if f.role == 'DEAN' else 0
            })
        pd.DataFrame(fac_data).to_csv(DATA_DIR / 'faculty_metadata.csv', index=False)
        self.stdout.write("Updated faculty_metadata.csv")

        # 2. Update rooms.csv
        rooms = Room.objects.select_related('building').all()
        room_data = []
        for r in rooms:
            room_data.append({
                'room_id': r.room_number,
                'building': r.building.name if r.building else 'Unknown',
                'floor': r.floor,
                'is_lab': 1 if r.room_type == 'LAB' else 0,
                'capacity': r.capacity,
                'floor_norm': r.floor / 5.0,
                'room_type': r.room_type.lower(),
                'lab_type': '',
                'is_shared': 1 if r.is_shared else 0,
                'is_active': 1 if r.is_active else 0,
                'notes': '',
            })
        pd.DataFrame(room_data).to_csv(DATA_DIR / 'rooms.csv', index=False)
        self.stdout.write("Updated rooms.csv")

        # 3. Update timeslots.csv
        if TimeSlot.objects.count() == 0:
            self.stdout.write("No timeslots found, seeding default grid...")
            from datetime import time as dt_time
            _SLOT_TIMES = [
                (1, dt_time(9, 40), dt_time(10, 35), False),
                (2, dt_time(10, 35), dt_time(11, 30), False),
                (3, dt_time(11, 30), dt_time(12, 25), False),
                (4, dt_time(12, 25), dt_time(13, 20), False),
                (99, dt_time(13, 20), dt_time(14, 15), True),   # LUNCH
                (5, dt_time(14, 15), dt_time(15, 10), False),
                (6, dt_time(15, 10), dt_time(16, 5), False),
            ]
            _SEED_DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
            bulk = []
            for day in _SEED_DAYS:
                for slot_num, start, end, is_lunch in _SLOT_TIMES:
                    bulk.append(TimeSlot(
                        day=day, slot_number=slot_num,
                        start_time=start, end_time=end, is_lunch=is_lunch,
                    ))
            TimeSlot.objects.bulk_create(bulk, ignore_conflicts=True)

        slots = TimeSlot.objects.all()
        slot_data = []
        DAY_MAP_INV = {"MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday"}
        for s in slots:
            slot_data.append({
                'day': DAY_MAP_INV.get(s.day, s.day),
                'slot_index': s.slot_number,
                'start_time': str(s.start_time),
                'end_time': str(s.end_time),
                'is_lunch': 1 if s.is_lunch else 0,
            })
        pd.DataFrame(slot_data).to_csv(DATA_DIR / 'timeslots.csv', index=False)
        self.stdout.write("Updated timeslots.csv")


        # Note: we don't regenerate timetable_dataset.csv automatically 
        # as it requires a valid schedule. We keep the historical one.
        self.stdout.write(self.style.SUCCESS("ML CSVs updated (Metadata only)."))
