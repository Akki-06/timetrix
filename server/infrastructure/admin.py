from django.contrib import admin
from .models import (
    Building,
    Room,
    ProgramRoomMapping,
)

admin.site.register(Building)
admin.site.register(Room)
admin.site.register(ProgramRoomMapping)
