from django.db import models
from academics.models import Courses

class Faculty(models.Model):
     ROLE_CHOICES = [
    ("DEAN", "Dean"),
    ("HOD", "Head of Department"),
    ("SENIOR", "Senior Faculty"),
    ("REGULAR", "Regular Faculty"),
    ("VISITING", "Visiting Faculty"),
    ]

     name = models.CharField(max_length=100)
     employee_id = models.CharField(max_length=10, unique=True)
     role = models.CharField(max_length=10, choices=ROLE_CHOICES)
     
     max_lectures_per_day = models.PositiveIntegerField(default=4)
     max_consecutive_lectures = models.PositiveIntegerField(default=2)
     
     def __str__(self):
          return f"{self.name} - {self.employee_id}"
      


class TeacherAvailability(models.Model):
    DAY_CHOICES = [
        ("MON", "Monday"),
        ("TUE", "Tuesday"),
        ("WED", "Wednesday"),
        ("THU", "Thursday"),
        ("FRI", "Friday"),
        ("SAT", "Saturday"),
    ]

    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="availabilities")
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    start_slot = models.PositiveIntegerField()
    end_slot = models.PositiveIntegerField()

    class Meta:
        unique_together = ("faculty", "day", "start_slot", "end_slot")

    def __str__(self):
        return f"{self.teacher.name} - {self.day} ({self.start_slot}-{self.end_slot})"

     
class FacultySubjectEligibility(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="eligible_subjects")
    course = models.ForeignKey(Courses, on_delete=models.CASCADE,related_name="eligible_faculty")

    class Meta:
        unique_together = ("faculty", "course")

    def __str__(self):
        return f"{self.teacher.name} → {self.course.code}"
