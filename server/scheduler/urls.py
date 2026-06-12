from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    TimeSlotViewSet,
    TimetableViewSet,
    LectureAllocationViewSet,
    GenerateTimetableView,
    SchedulerConfigView,
    NotificationViewSet,
    TimetableScheduleView,
)
from .sse_views import GenerateTimetableStreamView
from .editor_views import (
    EditorStartView,
    EditorMoveView,
    EditorDeleteView,
    EditorSaveView,
    EditorDiscardView,
    EditorPaletteView,
    EditorFreeRoomsView,
)

router = DefaultRouter()
router.register(r"timeslots",     TimeSlotViewSet)
router.register(r"timetables",   TimetableViewSet)
router.register(r"allocations",  LectureAllocationViewSet)
router.register(r"notifications", NotificationViewSet)

urlpatterns = router.urls + [
    path("generate/", GenerateTimetableView.as_view(), name="generate-timetable"),
    path(
        "generate-stream/",
        GenerateTimetableStreamView.as_view(),
        name="generate-timetable-stream",
    ),
    path("config/",   SchedulerConfigView.as_view(),   name="scheduler-config"),
    path("schedule/", TimetableScheduleView.as_view(), name="timetable-schedule"),

    # Editor — copy-on-edit with real-time DB sync
    path("editor/start/",   EditorStartView.as_view(),   name="editor-start"),
    path("editor/move/",    EditorMoveView.as_view(),    name="editor-move"),
    path("editor/delete/",  EditorDeleteView.as_view(),  name="editor-delete"),
    path("editor/save/",    EditorSaveView.as_view(),    name="editor-save"),
    path("editor/discard/", EditorDiscardView.as_view(), name="editor-discard"),
    path("editor/palette/", EditorPaletteView.as_view(), name="editor-palette"),
    path("editor/rooms/",   EditorFreeRoomsView.as_view(), name="editor-rooms"),
]