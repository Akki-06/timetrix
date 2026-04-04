from rest_framework import serializers
from .models import Faculty, TeacherAvailability, FacultySubjectEligibility


# ----------------------------
# FACULTY
# ----------------------------

class FacultySerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    def validate(self, data):
        if data["max_consecutive_lectures"] > data["max_lectures_per_day"]:
            raise serializers.ValidationError(
                "Max consecutive lectures cannot exceed max lectures per day."
            )
        return data

    class Meta:
        model = Faculty
        fields = "__all__"


# ----------------------------
# TEACHER AVAILABILITY
# ----------------------------

class TeacherAvailabilitySerializer(serializers.ModelSerializer):

    def validate(self, data):
        if data["start_slot"] >= data["end_slot"]:
            raise serializers.ValidationError(
                "Start slot must be less than end slot."
            )

        faculty = data["faculty"]
        day = data["day"]
        start = data["start_slot"]
        end = data["end_slot"]

        # Prevent overlapping availability blocks
        overlapping = TeacherAvailability.objects.filter(
            faculty=faculty,
            day=day
        ).filter(
            start_slot__lt=end,
            end_slot__gt=start
        )

        if overlapping.exists():
            raise serializers.ValidationError(
                "Availability block overlaps with existing availability."
            )

        return data

    class Meta:
        model = TeacherAvailability
        fields = "__all__"


# ----------------------------
# FACULTY SUBJECT ELIGIBILITY
# ----------------------------

class FacultySubjectEligibilitySerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source="faculty.name", read_only=True, default=None)
    course_code  = serializers.CharField(source="course.code", read_only=True, default=None)
    course_name  = serializers.CharField(source="course.name", read_only=True, default=None)

    def validate(self, data):
        if data.get("priority_weight", 1) <= 0:
            raise serializers.ValidationError(
                "Priority weight must be greater than zero."
            )
        return data

    class Meta:
        model = FacultySubjectEligibility
        fields = "__all__"