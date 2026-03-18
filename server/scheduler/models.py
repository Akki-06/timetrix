from django.db import models
from academics.models import AcademicTerm, CourseOffering, StudentGroup
from faculty.models import Faculty
from infrastructure.models import Room


# ----------------------------
# TIME SLOT MODEL
# ----------------------------

class TimeSlot(models.Model):

    class DayChoices(models.TextChoices):
        MON = "MON", "Monday"
        TUE = "TUE", "Tuesday"
        WED = "WED", "Wednesday"
        THU = "THU", "Thursday"
        FRI = "FRI", "Friday"

    day = models.CharField(max_length=3, choices=DayChoices.choices)
    slot_number = models.PositiveIntegerField()

    start_time = models.TimeField()
    end_time = models.TimeField()

    is_lunch = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["day", "slot_number"],
                name="unique_day_slot"
            )
        ]
        indexes = [
            models.Index(fields=["day"]),
        ]

    def __str__(self):
        return f"{self.day} - Slot {self.slot_number}"


# ----------------------------
# TIMETABLE VERSION MODEL
# ----------------------------

class Timetable(models.Model):

    term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.CASCADE,
        related_name="timetables"
    )

    version = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    is_finalized = models.BooleanField(default=False)

    total_constraint_score = models.FloatField(default=0.0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["term", "version"],
                name="unique_timetable_version_per_term"
            )
        ]
        indexes = [
            models.Index(fields=["term"]),
        ]

    def __str__(self):
        return f"{self.term} - Version {self.version}"


# ----------------------------
# LECTURE ALLOCATION
# ----------------------------

class LectureAllocation(models.Model):

    timetable = models.ForeignKey(
        Timetable,
        on_delete=models.CASCADE,
        related_name="allocations"
    )

    course_offering = models.ForeignKey(
        CourseOffering,
        on_delete=models.CASCADE
    )

    student_group = models.ForeignKey(
        StudentGroup,
        on_delete=models.CASCADE,
        related_name="lecture_allocations",
        editable=False,
        null=True,
        blank=True,
    )

    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.CASCADE
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE
    )

    timeslot = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE
    )

    # Constraint tracking
    hard_constraint_violated = models.BooleanField(default=False)
    soft_constraint_score = models.FloatField(default=0.0)

    class Meta:
        constraints = [
            # Room cannot be double-booked
            models.UniqueConstraint(
                fields=["timetable", "room", "timeslot"],
                name="unique_room_per_slot_per_timetable"
            ),

            # Faculty cannot teach two classes at same time
            models.UniqueConstraint(
                fields=["timetable", "faculty", "timeslot"],
                name="unique_faculty_per_slot_per_timetable"
            ),

            # Student group cannot have two classes at same time
            models.UniqueConstraint(
                fields=["timetable", "student_group", "timeslot"],
                name="unique_group_per_slot_per_timetable"
            ),
        ]

        indexes = [
            models.Index(fields=["faculty"]),
            models.Index(fields=["room"]),
            models.Index(fields=["timeslot"]),
            models.Index(fields=["timetable"]),
        ]

    def __str__(self):
        return f"{self.course_offering} - {self.timeslot}"

    def save(self, *args, **kwargs):
        if self.course_offering_id:
            self.student_group = self.course_offering.student_group
        super().save(*args, **kwargs)