from django.http import JsonResponse
from django.db.models.deletion import ProtectedError
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .checks import check_service
from .models import CheckRecord, DailyStat, Environment, Service, Team
from .serializers import (
    CheckRecordSerializer, DailyStatSerializer, EnvironmentSerializer,
    ServiceSerializer, TeamSerializer,
)


def healthz(request):
    """A local target for demonstrating the HTTP probe."""
    return JsonResponse({"status": "ok"})


class ProtectedDeleteMixin:
    def perform_destroy(self, instance):
        try:
            super().perform_destroy(instance)
        except ProtectedError as exc:
            raise ValidationError("Delete related services before deleting this item.") from exc


class EnvironmentViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Environment.objects.all().order_by("id")
    serializer_class = EnvironmentSerializer


class TeamViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Team.objects.all().order_by("id")
    serializer_class = TeamSerializer


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.select_related("environment", "team").all().order_by("id")
    serializer_class = ServiceSerializer

    @action(detail=True, methods=["post"])
    def check(self, request, pk=None):
        record = check_service(self.get_object())
        return Response(CheckRecordSerializer(record).data)


class CheckRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CheckRecordSerializer

    def get_queryset(self):
        queryset = CheckRecord.objects.all()
        service_id = self.request.query_params.get("service")
        if service_id:
            queryset = queryset.filter(service_id=service_id)
        return queryset


class DailyStatViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DailyStatSerializer

    def get_queryset(self):
        queryset = DailyStat.objects.all()
        for parameter in ("service", "environment", "team", "date"):
            value = self.request.query_params.get(parameter)
            if value:
                queryset = queryset.filter(**{parameter + ("_id" if parameter != "date" else ""): value})
        return queryset
