import secrets
from datetime import date, datetime, time, timedelta

from celery import shared_task
from django.db.models import Count, Q
from django.utils import timezone

from .models import CheckRecord, DailyStat, Service


@shared_task
def rotate_service_tokens():
    """Rotate encrypted local credentials; external target synchronization is unspecified."""
    count = 0
    for service in Service.objects.iterator():
        service.set_token(secrets.token_urlsafe(32))
        service.save(update_fields=["token_ciphertext", "token_rotated_at"])
        count += 1
    return count


@shared_task
def summarize_daily_health(stat_date=None):
    """Store results for yesterday, or an explicit YYYY-MM-DD day for verification."""
    stat_date = date.fromisoformat(stat_date) if stat_date else timezone.localdate() - timedelta(days=1)
    next_date = stat_date + timedelta(days=1)
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(stat_date, time.min), tz)
    end = timezone.make_aware(datetime.combine(next_date, time.min), tz)

    counts = {
        row["service_id"]: row
        for row in CheckRecord.objects.filter(checked_at__gte=start, checked_at__lt=end)
        .order_by()
        .values("service_id")
        .annotate(total=Count("id"), success=Count("id", filter=Q(success=True)))
    }

    for service in Service.objects.filter(created_at__lt=end).iterator():
        row = counts.get(service.id, {"total": 0, "success": 0})
        total = row["total"]
        success = row["success"]
        DailyStat.objects.update_or_create(
            service=service,
            date=stat_date,
            defaults={
                "environment": service.environment,
                "team": service.team,
                "total_count": total,
                "success_count": success,
                "health_rate": success / total if total else None,
            },
        )
    return stat_date.isoformat()
