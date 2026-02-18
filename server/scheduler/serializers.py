from rest_framework import serializers
from .models import Timetable, TimeSlot, LectureAllocation


class TimeSlotSerializer(serializers.ModelSerializer):

    def validate(self, data):
        if data["start_time"] >= data["end_time"]:
            raise serializers.ValidationError(
                "Start time must be earlier than end time."
            )
        return data

    class Meta:
        model = TimeSlot
        fields = "__all__"

        
class TimetableSerializer(serializers.ModelSerializer):

    class Meta:
        model = Timetable
        fields = "__all__"


class LectureAllocationSerializer(serializers.ModelSerializer):

    def validate(self, data):

        timetable = data["timetable"]
        timeslot = data["timeslot"]
        faculty = data["faculty"]
        room = data["room"]
        course_offering = data["course_offering"]

        # 🔹 Check Faculty Clash
        if LectureAllocation.objects.filter(
            timetable=timetable,
            timeslot=timeslot,
            faculty=faculty
        ).exists():
            raise serializers.ValidationError(
                "Faculty already assigned in this time slot."
            )

        # 🔹 Check Student Group Clash
        if LectureAllocation.objects.filter(
            timetable=timetable,
            timeslot=timeslot,
            course_offering__student_group=course_offering.student_group
        ).exists():
            raise serializers.ValidationError(
                "Student group already has a lecture in this slot."
            )

        return data

    class Meta:
        model = LectureAllocation
        fields = "__all__"
