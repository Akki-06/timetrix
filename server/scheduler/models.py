from django.db import models
from academics.models import AcademicTerm, CourseOffering, StudentGroup
from faculty.models import Faculty
from infrastructure.models import Room


# ----------------------------
# SCHEDULER CONFIG (singleton)
# ----------------------------

class SchedulerConfig(models.Model):
    """
    Global scheduler settings. Always exactly one row (pk=1).
    Use SchedulerConfig.get() everywhere — never instantiate directly.
    """

    academic_year = models.CharField(max_length=20, default="2025-26")

    # Faculty weekly hour caps by role
    max_hours_dean     = models.PositiveIntegerField(default=6)
    max_hours_hod      = models.PositiveIntegerField(default=12)
    max_hours_senior   = models.PositiveIntegerField(default=16)
    max_hours_regular  = models.PositiveIntegerField(default=18)
    max_hours_visiting = models.PositiveIntegerField(default=8)

    # Hard scheduling constraints
    max_lectures_per_day     = models.PositiveIntegerField(default=4)
    max_consecutive_lectures = models.PositiveIntegerField(default=2)

    # Scheduling behaviour toggles
    allow_weekend_classes         = models.BooleanField(default=False)
    enforce_room_type             = models.BooleanField(default=True)
    enforce_faculty_availability  = models.BooleanField(default=True)
    prioritize_senior_faculty     = models.BooleanField(default=True)
    auto_publish_timetable        = models.BooleanField(default=False)

    # Notification preferences
    notify_on_generation_complete = models.BooleanField(default=True)
    notify_on_failed_generation   = models.BooleanField(default=True)

    # History
    keep_history_versions = models.PositiveIntegerField(default=20)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def role_cap(self, role: str) -> int:
        """Return the configured weekly hour cap for a given faculty role."""
        return {
            "DEAN"    : self.max_hours_dean,
            "HOD"     : self.max_hours_hod,
            "SENIOR"  : self.max_hours_senior,
            "REGULAR" : self.max_hours_regular,
            "VISITING": self.max_hours_visiting,
        }.get(role, self.max_hours_regular)

    class Meta:
        verbose_name = "Scheduler Configuration"

    def __str__(self):
        return f"SchedulerConfig ({self.academic_year})"


# ----------------------------
# IN-APP NOTIFICATIONS
# ----------------------------

class Notification(models.Model):

    class Type(models.TextChoices):
        INFO    = "info",    "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR   = "error",   "Error"

    message    = models.CharField(max_length=500)
    type       = models.CharField(max_length=10, choices=Type.choices, default=Type.INFO)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes  = [models.Index(fields=["is_read"])]

    def __str__(self):
        return f"[{self.type.upper()}] {self.message[:60]}"


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
        SAT = "SAT", "Saturday"

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