from django.db import models
from academics.models import Program


# ----------------------------
# BUILDING MODEL
# ----------------------------

class Building(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    floors = models.PositiveIntegerField()

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ----------------------------
# ROOM MODEL
# ----------------------------

class Room(models.Model):

    class RoomType(models.TextChoices):
        THEORY = "THEORY", "Theory Classroom"
        LAB = "LAB", "Laboratory"

    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="rooms"
    )

    room_number = models.CharField(max_length=20)
    floor = models.PositiveIntegerField()

    capacity = models.PositiveIntegerField()

    room_type = models.CharField(
        max_length=10,
        choices=RoomType.choices
    )

    is_active = models.BooleanField(default=True)

    # Constraint Support
    is_shared = models.BooleanField(default=True)  # Can multiple programs use it?
    priority_weight = models.PositiveIntegerField(default=1)  # For optimization preference

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["building", "room_number"],
                name="unique_room_per_building"
            )
        ]
        indexes = [
            models.Index(fields=["room_type"]),
            models.Index(fields=["capacity"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.building.code}-{self.room_number}"


# ----------------------------
# PROGRAM-ROOM MAPPING
# ----------------------------

class ProgramRoomMapping(models.Model):
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="room_mappings"
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="program_mappings"
    )

    priority_weight = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["program", "room"],
                name="unique_program_room_pair"
            )
        ]
        indexes = [
            models.Index(fields=["program"]),
            models.Index(fields=["room"]),
        ]

    def __str__(self):
        return f"{self.program.code} → {self.room}"