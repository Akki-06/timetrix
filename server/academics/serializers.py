from rest_framework import serializers
from .models import (
    Department,
    Program,
    AcademicTerm,
    Course,
    StudentGroup,
    CourseOffering
)

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"
        
class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = "__all__"
        
class AcademicTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicTerm
        fields = "__all__"

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
        
class StudentGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentGroup
        fields = "__all__"


class CourseOfferingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseOffering
        fields = "__all__"
