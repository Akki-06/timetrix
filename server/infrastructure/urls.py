from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import BuildingViewSet, RoomViewSet, ProgramRoomMappingViewSet, RoomBulkUploadView

router = DefaultRouter()
router.register(r'building', BuildingViewSet)
router.register(r'room', RoomViewSet)
router.register(r'program-room-map', ProgramRoomMappingViewSet)

urlpatterns = [
    path("room/bulk-upload/", RoomBulkUploadView.as_view(), name="room-bulk-upload"),
] + router.urls