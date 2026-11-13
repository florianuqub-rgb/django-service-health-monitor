from rest_framework.routers import DefaultRouter

from .views import (
    CheckRecordViewSet, DailyStatViewSet, EnvironmentViewSet,
    ServiceViewSet, TeamViewSet,
)

router = DefaultRouter()
router.register("environments", EnvironmentViewSet)
router.register("teams", TeamViewSet)
router.register("services", ServiceViewSet)
router.register("checks", CheckRecordViewSet, basename="checks")
router.register("stats", DailyStatViewSet, basename="stats")

urlpatterns = router.urls
