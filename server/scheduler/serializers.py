from rest_framework import serializers
from .models import Timetable, TimeSlot, LectureAllocation


# ----------------------------
# TIME SLOT
# ----------------------------

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


# ----------------------------
# TIMETABLE
# ----------------------------

class TimetableSerializer(serializers.ModelSerializer):

    class Meta:
        model = Timetable
        fields = "__all__"
        read_only_fields = ["created_at", "total_constraint_score"]


# ----------------------------
# LECTURE ALLOCATION
# ----------------------------

class LectureAllocationSerializer(serializers.ModelSerializer):

    def validate(self, data):

        timetable = data["timetable"]
        timeslot = data["timeslot"]
        faculty = data["faculty"]
        room = data["room"]
        course_offering = data["course_offering"]

        # Prevent modification of finalized timetable
        if timetable.is_finalized:
            raise serializers.ValidationError(
                "Cannot modify a finalized timetable."
            )

        # Ensure course offering belongs to same term
        if course_offering.student_group.term != timetable.term:
            raise serializers.ValidationError(
                "Course offering does not belong to this timetable term."
            )

        # 🔹 Faculty Clash
        if LectureAllocation.objects.filter(
            timetable=timetable,
            timeslot=timeslot,
            faculty=faculty
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError(
                "Faculty already assigned in this time slot."
            )

        # 🔹 Room Clash
        if LectureAllocation.objects.filter(
            timetable=timetable,
            timeslot=timeslot,
            room=room
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError(
                "Room already occupied in this time slot."
            )

        # 🔹 Student Group Clash
        if LectureAllocation.objects.filter(
            timetable=timetable,
            timeslot=timeslot,
            course_offering__student_group=course_offering.student_group
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError(
                "Student group already has a lecture in this slot."
            )

        # 🔹 Room Capacity Check
        if course_offering.student_group.strength > room.capacity:
            raise serializers.ValidationError(
                "Room capacity is insufficient for this student group."
            )

        return data

    class Meta:
        model = LectureAllocation
        fields = "__all__"
        read_only_fields = ["student_group"]