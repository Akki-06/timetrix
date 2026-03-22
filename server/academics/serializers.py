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
    class Meta:
        model = Program
        fields = "__all__"


# ----------------------------
# ACADEMIC TERM
# ----------------------------

class AcademicTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicTerm
        fields = "__all__"


# ----------------------------
# COURSE
# ----------------------------

class CourseSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name", read_only=True, default=None)

    def validate(self, data):
        return data

    class Meta:
        model = Course
        fields = "__all__"


# ----------------------------
# STUDENT GROUP
# ----------------------------

class StudentGroupSerializer(serializers.ModelSerializer):

    def validate(self, data):
        if data["strength"] <= 0:
            raise serializers.ValidationError(
                "Student group strength must be greater than zero."
            )
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