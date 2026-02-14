from rest_framework import viewsets
from .models import *
from .serializers import *
    
class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer
    
class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    
class ProgramRoomMappingViewSet(viewsets.ModelViewSet):
    queryset = ProgramRoomMapping.objects.all()
    serializer_class = ProgramRoomMappingSerializer