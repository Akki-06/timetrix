from rest_framework import viewsets, filters, status
from rest_framework.response import Response
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

    def create(self, request, *args, **kwargs):
        """Upsert on building code — idempotent bulk upload."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code     = serializer.validated_data["code"]
        defaults = {k: v for k, v in serializer.validated_data.items() if k != "code"}

        building, created = Building.objects.update_or_create(
            code=code, defaults=defaults
        )

        out = self.get_serializer(building)
        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(out.data, status=http_status)


# ----------------------------
# ROOM
# ----------------------------

class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.select_related("building")
    serializer_class = RoomSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["building", "room_type", "is_active"]
    search_fields = ["room_number"]

    def create(self, request, *args, **kwargs):
        """
        Upsert: if a room with the same (building, room_number) already
        exists, update it instead of failing with a uniqueness error.
        This makes bulk uploads from rooms.csv idempotent.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        building    = serializer.validated_data["building"]
        room_number = serializer.validated_data["room_number"]
        defaults    = {
            k: v for k, v in serializer.validated_data.items()
            if k not in ("building", "room_number")
        }

        room, created = Room.objects.update_or_create(
            building=building,
            room_number=room_number,
            defaults=defaults,
        )

        out = self.get_serializer(room)
        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(out.data, status=http_status)


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