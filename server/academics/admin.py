from django.contrib import admin
from .models import (
    Department,
    Program,
    AcademicTerm,
    Course,
    StudentGroup,
    CourseOffering,
)

admin.site.register(Department)
admin.site.register(Program)
admin.site.register(AcademicTerm)
admin.site.register(Course)
admin.site.register(StudentGroup)
admin.site.register(CourseOffering)
