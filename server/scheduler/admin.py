from django.contrib import admin
from .models import (
   TimeSlot,
   Timetable,
   LectureAllocation
)

admin.site.register(TimeSlot)
admin.site.register(Timetable)
admin.site.register(LectureAllocation)
