from django.db import models
from academics.models import Course


class Faculty(models.Model):

    class RoleChoices(models.TextChoices):
        DEAN = "DEAN", "Dean"
        HOD = "HOD", "Head of Department"
        SENIOR = "SENIOR", "Senior Faculty"
        REGULAR = "REGULAR", "Regular Faculty"
        VISITING = "VISITING", "Visiting Faculty"

    name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=20, unique=True)

    role = models.CharField(
        max_length=10,
        choices=RoleChoices.choices,
        default=RoleChoices.REGULAR
    )

    max_lectures_per_day = models.PositiveIntegerField(default=4)
    max_consecutive_lectures = models.PositiveIntegerField(default=2)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.employee_id}"

      


class TeacherAvailability(models.Model):

    class DayChoices(models.TextChoices):
        MON = "MON", "Monday"
        TUE = "TUE", "Tuesday"
        WED = "WED", "Wednesday"
        THU = "THU", "Thursday"
        FRI = "FRI", "Friday"
        SAT = "SAT", "Saturday"

    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.CASCADE,
        related_name="availabilities"
    )

    day = models.CharField(
        max_length=3,
        choices=DayChoices.choices
    )

    start_slot = models.PositiveIntegerField()
    end_slot = models.PositiveIntegerField()

    class Meta:
        unique_together = ("faculty", "day", "start_slot", "end_slot")

    def __str__(self):
        return f"{self.faculty.name} - {self.day} ({self.start_slot}-{self.end_slot})"


class FacultySubjectEligibility(models.Model):
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.CASCADE,
        related_name="eligible_subjects"
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="eligible_faculty"
    )

    class Meta:
        unique_together = ("faculty", "course")

    def __str__(self):
        return f"{self.faculty.name} → {self.course.code}"

