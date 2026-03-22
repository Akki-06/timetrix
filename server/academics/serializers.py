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

    def validate(self, data):
        return data

    class Meta:
        model = CourseOffering
        fields = "__all__"