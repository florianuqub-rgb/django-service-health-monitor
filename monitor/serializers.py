from urllib.parse import urlsplit

from rest_framework import serializers
from rest_framework.reverse import reverse

from .models import CheckRecord, DailyStat, Environment, Service, Team


class EnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Environment
        fields = ["id", "code"]


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name"]


class ServiceSerializer(serializers.ModelSerializer):
    token = serializers.CharField(write_only=True, required=False, allow_blank=False)
    links = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            "id", "name", "base_url", "health_path", "environment", "team",
            "token", "token_rotated_at", "created_at", "links",
        ]
        read_only_fields = ["id", "token_rotated_at", "created_at"]

    def validate_base_url(self, value):
        parsed = urlsplit(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/")):
            raise serializers.ValidationError("Use an http(s) origin without a path or credentials.")
        return value.rstrip("/")

    def get_links(self, obj):
        request = self.context.get("request")
        return {
            "detail": reverse("service-detail", args=[obj.pk], request=request),
            "check": reverse("service-check", args=[obj.pk], request=request),
            "checks": f"{reverse('checks-list', request=request)}?service={obj.pk}",
            "stats": f"{reverse('stats-list', request=request)}?service={obj.pk}",
        }

    def validate_health_path(self, value):
        if not value.startswith("/") or value.startswith("//") or "?" in value or "#" in value:
            raise serializers.ValidationError("Use a path beginning with one slash, without a query.")
        return value

    def create(self, validated_data):
        token = validated_data.pop("token", None)
        service = Service(**validated_data)
        if token:
            service.set_token(token)
        service.save()
        return service

    def update(self, instance, validated_data):
        token = validated_data.pop("token", None)
        for name, value in validated_data.items():
            setattr(instance, name, value)
        if token:
            instance.set_token(token)
        instance.save()
        return instance


class CheckRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckRecord
        fields = ["id", "service", "checked_at", "success", "status_code", "duration_ms", "error_message"]


class DailyStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyStat
        fields = [
            "id", "service", "environment", "team", "date",
            "success_count", "total_count", "health_rate", "calculated_at",
        ]
