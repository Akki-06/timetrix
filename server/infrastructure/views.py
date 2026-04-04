from rest_framework import viewsets, filters, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
import logging

log = logging.getLogger(__name__)

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


# ----------------------------
# ROOM BULK UPLOAD (CSV / XLSX)
# ----------------------------

_ROOM_TYPE_MAP = {
    "theory": "THEORY", "lecture": "THEORY", "classroom": "THEORY",
    "lab": "LAB", "laboratory": "LAB",
}


class RoomBulkUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fname = file.name.lower()
        rows = []

        # ── Read CSV ──
        if fname.endswith(".csv"):
            import csv, io
            text = file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            for r in reader:
                rows.append({k.strip().lower().replace(" ", "_"): v for k, v in r.items()})

        # ── Read XLSX ──
        elif fname.endswith(".xlsx"):
            try:
                import openpyxl
            except ImportError:
                return Response(
                    {"error": "openpyxl not installed."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            wb = openpyxl.load_workbook(file, read_only=True)
            ws = wb.active
            raw = list(ws.iter_rows(values_only=True))
            if len(raw) < 2:
                return Response({"error": "File needs header + data rows."}, status=400)
            header = [str(h).strip().lower().replace(" ", "_") if h else "" for h in raw[0]]
            for r in raw[1:]:
                rows.append(dict(zip(header, r)))
        else:
            return Response(
                {"error": "Only .csv and .xlsx files are supported."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not rows:
            return Response({"error": "No data rows found."}, status=400)

        created = 0
        updated = 0
        errors = []

        with transaction.atomic():
            for row_num, row in enumerate(rows, start=2):
                try:
                    # Building code — auto-create
                    bldg_code = str(
                        row.get("building_code") or row.get("building") or ""
                    ).strip().upper()

                    if not bldg_code:
                        errors.append(f"Row {row_num}: missing building code, skipped.")
                        continue

                    # Derive max floor from rows to set building floors
                    floor_val = int(row.get("floor", 0) or 0)
                    building, bldg_created = Building.objects.get_or_create(
                        code__iexact=bldg_code,
                        defaults={
                            "code": bldg_code,
                            "name": bldg_code,
                            "floors": max(floor_val + 1, 1),
                            "is_active": True,
                        },
                    )
                    if bldg_created:
                        log.info(f"Auto-created building '{bldg_code}'")
                    elif floor_val + 1 > building.floors:
                        building.floors = floor_val + 1
                        building.save(update_fields=["floors"])

                    # Room number
                    room_number = str(
                        row.get("room_number") or row.get("room_id") or ""
                    ).strip()
                    if not room_number:
                        errors.append(f"Row {row_num}: missing room_number, skipped.")
                        continue

                    # Room type
                    rt_raw = str(row.get("room_type", "theory")).strip().lower()
                    room_type = _ROOM_TYPE_MAP.get(rt_raw, rt_raw.upper())
                    if room_type not in ("THEORY", "LAB"):
                        room_type = "THEORY"

                    capacity = int(row.get("capacity", 40) or 40)
                    is_active = str(row.get("is_active", "1")).strip() in ("1", "true", "True", "yes")
                    is_shared = str(row.get("is_shared", "1")).strip() in ("1", "true", "True", "yes")
                    priority = int(row.get("priority_weight", 1) or 1)

                    room, was_created = Room.objects.update_or_create(
                        building=building,
                        room_number=room_number,
                        defaults={
                            "floor": floor_val,
                            "capacity": capacity,
                            "room_type": room_type,
                            "is_active": is_active,
                            "is_shared": is_shared,
                            "priority_weight": priority,
                        },
                    )

                    if was_created:
                        created += 1
                    else:
                        updated += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {e}")

        return Response(
            {"created": created, "updated": updated, "errors": errors},
            status=status.HTTP_200_OK,
        )