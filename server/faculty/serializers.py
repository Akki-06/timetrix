from rest_framework import serializers
from .models import *

class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = "__all__"

class TeacherAvailabilitySerializer(serializers.ModelSerializer):

    def validate(self, data):
        if data["start_slot"] >= data["end_slot"]:
            raise serializers.ValidationError(
                "Start slot must be less than end slot."
            )
        return data

    class Meta:
        model = TeacherAvailability
        fields = "__all__"

class FacultySubjectEligibilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = FacultySubjectEligibility
        fields = "__all__"
