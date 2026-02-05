from django.db import models
from academics.models import Program


class Building(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    floors = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.name} ({self.code})"


class Room(models.Model):
    ROOM_TYPE_CHOICES = [
        ("THEORY", "Theory Classroom"),
        ("LAB", "Laboratory"),
    ]

    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="rooms")
    room_number = models.CharField(max_length=20)
    floor = models.PositiveIntegerField()
    capacity = models.PositiveIntegerField()
    room_type = models.CharField(max_length=10, choices=ROOM_TYPE_CHOICES)

    class Meta:
        unique_together = ("building", "room_number")

    def __str__(self):
        return f"{self.building.code}-{self.room_number}"
    

class ProgramRoomMapping(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="room_mappings")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="program_mappings")

    class Meta:
        unique_together = ("program", "room")

    def __str__(self):
        return f"{self.program.code} → {self.room}"

