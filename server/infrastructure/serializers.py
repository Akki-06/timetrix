from rest_framework import serializers
from .models import Building, Room, ProgramRoomMapping


# ----------------------------
# BUILDING
# ----------------------------

class BuildingSerializer(serializers.ModelSerializer):

    def validate_floors(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Building must have at least one floor."
            )
        return value

    class Meta:
        model = Building
        fields = "__all__"


# ----------------------------
# ROOM
# ----------------------------

class RoomSerializer(serializers.ModelSerializer):

    def validate(self, data):
        building = data["building"]
        floor = data["floor"]
        capacity = data["capacity"]
        priority_weight = data.get("priority_weight", 1)

        if capacity <= 0:
            raise serializers.ValidationError(
                "Capacity must be greater than zero."
            )

        if floor > building.floors:
            raise serializers.ValidationError(
                "Room floor cannot exceed total floors of building."
            )

        if priority_weight <= 0:
            raise serializers.ValidationError(
                "Priority weight must be greater than zero."
            )

        return data

    class Meta:
        model = Room
        fields = "__all__"


# ----------------------------
# PROGRAM ROOM MAPPING
# ----------------------------

class ProgramRoomMappingSerializer(serializers.ModelSerializer):

    def validate(self, data):
        if data.get("priority_weight", 1) <= 0:
            raise serializers.ValidationError(
                "Priority weight must be greater than zero."
            )
        return data

    class Meta:
        model = ProgramRoomMapping
        fields = "__all__"