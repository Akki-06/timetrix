from rest_framework import serializers
from .models import (
    Faculty, TeacherAvailability, FacultySubjectEligibility,
    FacultyProgramExclusion, FacultySemesterExclusion,
)


# ----------------------------
# FACULTY
# ----------------------------

class FacultySerializer(serializers.ModelSerializer):
    # Primary: the FK on Faculty itself.
    # Fallback: derived from the department of programs whose courses this
    # faculty is assigned to. Without this, faculty rows without an explicit
    # department FK fall into a useless "Unassigned" bucket on the UI even
    # though we can infer a sensible department from their workload.
    department_name = serializers.SerializerMethodField()

    def get_department_name(self, obj):
        if obj.department_id and obj.department:
            return obj.department.name

        # Derived fallback: most-common department across assigned offerings.
        # One query per row is fine on the list endpoint (≤ 100 faculty), and
        # ModelViewSet.list isn't a hot path.
        from collections import Counter
        from academics.models import CourseOffering
        depts = (
            CourseOffering.objects
            .filter(assigned_faculty=obj)
            .select_related("course__program__department")
            .values_list("course__program__department__name", flat=True)
        )
        names = [d for d in depts if d]
        if not names:
            return None
        return Counter(names).most_common(1)[0][0]

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


# ----------------------------
# FACULTY PROGRAM EXCLUSION
# ----------------------------

class FacultyProgramExclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacultyProgramExclusion
        fields = "__all__"


# ----------------------------
# FACULTY SEMESTER EXCLUSION
# ----------------------------

class FacultySemesterExclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacultySemesterExclusion
        fields = "__all__"