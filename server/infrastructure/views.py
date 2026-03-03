from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Building, Room, ProgramRoomMapping
from .serializers import (
    BuildingSerializer,
    RoomSerializer,
    ProgramRoomMappingSerializer
)


# ----------------------------
# BUILDING
# ----------------------------

class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "code"]


# ----------------------------
# ROOM
# ----------------------------

class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.select_related("building")
    serializer_class = RoomSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["building", "room_type", "is_active"]
    search_fields = ["room_number"]


# ----------------------------
# PROGRAM ROOM MAPPING
# ----------------------------

class ProgramRoomMappingViewSet(viewsets.ModelViewSet):
    queryset = ProgramRoomMapping.objects.select_related(
        "program",
        "room",
        "room__building"
    )
    serializer_class = ProgramRoomMappingSerializer

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["program", "room"]