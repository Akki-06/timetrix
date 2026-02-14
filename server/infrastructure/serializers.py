from rest_framework import serializers
from .models import *

class BuildingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields  = "__all__"
        

class RoomSerializer(serializers.ModelSerializer):

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Capacity must be positive.")
        return value

    class Meta:
        model = Room
        fields = "__all__"
    
class ProgramRoomMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramRoomMapping
        fields = "__all__"
