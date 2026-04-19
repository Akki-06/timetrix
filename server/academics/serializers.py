from rest_framework import serializers
from .models import (
    Department,
    Program,
    AcademicTerm,
    Course,
    StudentGroup,
    CourseOffering
)


# ----------------------------
# DEPARTMENT
# ----------------------------

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


# ----------------------------
# PROGRAM
# ----------------------------

class ProgramSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Program
        fields = "__all__"


# ----------------------------
# ACADEMIC TERM
# ----------------------------

class AcademicTermSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.display_name", read_only=True, default=None)
    program_code = serializers.CharField(source="program.code", read_only=True, default=None)

    class Meta:
        model = AcademicTerm
        fields = "__all__"


# ----------------------------
# COURSE
# ----------------------------

class CourseSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.display_name", read_only=True, default=None)
    # Human-readable code with internal program suffix stripped (e.g. 24COA191 not 24COA191_BCA)
    display_code = serializers.CharField(read_only=True)

    def validate(self, data):
        return data

    class Meta:
        model = Course
        fields = "__all__"


# ----------------------------
# STUDENT GROUP
# ----------------------------

class StudentGroupSerializer(serializers.ModelSerializer):
    # Read-only context fields so the frontend can display program/semester without extra calls
    program_id   = serializers.IntegerField(source="term.program.id",           read_only=True)
    program_name = serializers.CharField(source="term.program.display_name",    read_only=True)
    program_code = serializers.CharField(source="term.program.code",            read_only=True)
    semester     = serializers.IntegerField(source="term.semester",             read_only=True)
    year         = serializers.IntegerField(source="term.year",                 read_only=True)

    def validate(self, data):
        if data.get("strength", 1) <= 0:
            raise serializers.ValidationError("Student group strength must be greater than zero.")
        return data

    class Meta:
        model = StudentGroup
        fields = "__all__"


# ----------------------------
# COURSE OFFERING
# ----------------------------

class CourseOfferingSerializer(serializers.ModelSerializer):
    course_code         = serializers.CharField(source="course.code",         read_only=True, default=None)
    # Display-friendly code with internal suffix stripped — USE THIS on the frontend
    course_display_code = serializers.CharField(source="course.display_code", read_only=True, default=None)
    course_name    = serializers.CharField(source="course.name",         read_only=True, default=None)
    course_type    = serializers.CharField(source="course.course_type",   read_only=True, default=None)
    credits        = serializers.IntegerField(source="course.credits",   read_only=True, default=0)
    course_semester = serializers.IntegerField(source="course.semester", read_only=True, default=None)
    faculty_name   = serializers.CharField(source="assigned_faculty.name", read_only=True, default=None)
    section_name   = serializers.CharField(source="student_group.name",  read_only=True, default=None)

    def validate(self, data):
        return data

    class Meta:
        model = CourseOffering
        fields = "__all__"