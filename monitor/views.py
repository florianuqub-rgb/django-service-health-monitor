from datetime import timedelta

from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
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


def dashboard(request):
    context = {"can_manage": request.user.is_authenticated and request.user.is_staff}
    if context["can_manage"]:
        yesterday = timezone.localdate() - timedelta(days=1)
        stats = DailyStat.objects.filter(date=yesterday).select_related("service").order_by("service__name")
        context.update({
            "environment_count": Environment.objects.count(),
            "team_count": Team.objects.count(),
            "service_count": Service.objects.count(),
            "services": Service.objects.select_related("environment", "team").order_by("environment__code", "name"),
            "recent_checks": CheckRecord.objects.select_related("service").order_by("-checked_at")[:8],
            "yesterday": yesterday,
            "daily_stats": [
                {"stat": stat, "rate": f"{stat.health_rate * 100:.0f}%" if stat.health_rate is not None else "暂无巡检"}
                for stat in stats
            ],
        })
    return render(request, "monitor/dashboard.html", context)


@require_POST
def dashboard_check(request, service_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseForbidden("需要管理员登录。")
    service = get_object_or_404(Service, pk=service_id)
    record = check_service(service)
    status = record.status_code or "无响应"
    if record.success:
        messages.success(request, f"{service.name}：巡检成功，状态码 {status}。")
    else:
        messages.warning(request, f"{service.name}：巡检失败，状态码 {status}。")
    return redirect("dashboard")


@require_GET
def demo_target_ok(request):
    return JsonResponse({"demo": True, "status": "ok"})


@require_GET
def demo_target_unavailable(request):
    return JsonResponse({"demo": True, "status": "unavailable"}, status=503)


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
