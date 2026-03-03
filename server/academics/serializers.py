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

    def validate(self, data):
        if data["min_weekly_lectures"] > data["max_weekly_lectures"]:
            raise serializers.ValidationError(
                "Minimum lectures cannot exceed maximum lectures."
            )
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
        course = data["course"]
        student_group = data["student_group"]

        # Optional logical validation:
        # Prevent assigning LAB course without lab requirement
        if course.requires_lab_room and course.course_type != "LAB":
            raise serializers.ValidationError(
                "Course marked as requiring lab must be of LAB type."
            )

        return data

    class Meta:
        model = CourseOffering
        fields = "__all__"