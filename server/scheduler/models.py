from django.db import models
from academics.models import AcademicTerm, CourseOffering
from faculty.models import Faculty
from infrastructure.models import Room

class TimeSlot(models.Model):
    
    DAY_CHOICES = [
        ("MON", "Monday"),
        ("TUE", "Tuesday"),
        ("WED", "Wednesday"),
        ("THU", "Thursday"),
        ("FRI", "Friday"),
        ("SAT", "Saturday"),
    ]
    
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    slot_number = models.PositiveIntegerField()
    
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    is_lunch = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ("day", "slot_number")
        
    def __str__(self):
        return f"{self.day} - Slot {self.slot_number}"
   
   
 
class Timetable(models.Model):

    term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.CASCADE,
        related_name="timetables"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    is_finalized = models.BooleanField(default=False)

    version = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.term} - Version {self.version}"
    
    
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

    class Meta:
        unique_together = ("room", "timeslot", "timetable")

    def __str__(self):
        return f"{self.course_offering} - {self.timeslot}"



