from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'building',BuildingViewSet)
router.register(r'room',RoomViewSet)
router.register(r'program-room-map',ProgramRoomMappingViewSet)

urlpatterns = router.urls