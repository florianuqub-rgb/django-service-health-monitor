from django.contrib import admin

from .models import CheckRecord, DailyStat, Environment, Service, Team


admin.site.register(Environment)
admin.site.register(Team)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "environment", "team", "base_url", "token_rotated_at")
    list_filter = ("environment", "team")
    search_fields = ("name", "base_url")
    exclude = ("token_ciphertext",)
    readonly_fields = ("token_rotated_at", "created_at")


@admin.register(CheckRecord)
class CheckRecordAdmin(admin.ModelAdmin):
    list_display = ("service", "checked_at", "success", "status_code", "duration_ms")
    list_filter = ("success", "service__environment", "service__team")
    readonly_fields = ("service", "checked_at", "success", "status_code", "duration_ms", "error_message")

    def has_add_permission(self, request):
        return False


@admin.register(DailyStat)
class DailyStatAdmin(admin.ModelAdmin):
    list_display = ("service", "date", "environment", "team", "health_rate")
    list_filter = ("date", "environment", "team")
    readonly_fields = (
        "service", "environment", "team", "date", "success_count",
        "total_count", "health_rate", "calculated_at",
    )

    def has_add_permission(self, request):
        return False
