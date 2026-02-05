from django.contrib import admin
from .models import (
    Faculty,
    TeacherAvailability,
    FacultySubjectEligibility,
)

admin.site.register(Faculty)
admin.site.register(TeacherAvailability)
admin.site.register(FacultySubjectEligibility)
