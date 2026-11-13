from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from monitor.models import CheckRecord, Environment, Service, Team
from monitor.tasks import summarize_daily_health


EXAMPLES = (
    ("演示 · 订单 API", "dev", "演示 · 订单组", "/demo-target/ok/", (True, True, True)),
    ("演示 · 订单 API", "test", "演示 · 订单组", "/demo-target/unavailable/", (True, False, False)),
    ("演示 · 支付 API", "prod", "演示 · 支付组", "/demo-target/ok/", (True, True, True)),
    ("演示 · 库存 API", "prod", "演示 · 平台组", "/demo-target/unavailable/", (False, True, False)),
)


class Command(BaseCommand):
    help = "Add clearly labeled example services, historical checks, and daily stats."

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default="http://127.0.0.1:8000")

    @transaction.atomic
    def handle(self, *args, **options):
        base_url = options["base_url"].rstrip("/")
        environments = {
            code: Environment.objects.get_or_create(code=code)[0]
            for code in ("dev", "test", "prod")
        }
        teams = {
            name: Team.objects.get_or_create(name=name)[0]
            for name in ("演示 · 订单组", "演示 · 支付组", "演示 · 平台组")
        }
        yesterday = timezone.localdate() - timedelta(days=1)
        check_times = (time(9, 0), time(12, 30), time(16, 0))

        for name, environment_code, team_name, health_path, outcomes in EXAMPLES:
            service, created = Service.objects.get_or_create(
                name=name,
                environment=environments[environment_code],
                defaults={
                    "team": teams[team_name],
                    "base_url": base_url,
                    "health_path": health_path,
                },
            )
            if created:
                Service.objects.filter(pk=service.pk).update(
                    created_at=timezone.make_aware(datetime.combine(yesterday, time(8, 0)))
                )
            for check_time, success in zip(check_times, outcomes):
                checked_at = timezone.make_aware(datetime.combine(yesterday, check_time))
                CheckRecord.objects.get_or_create(
                    service=service,
                    checked_at=checked_at,
                    defaults={
                        "success": success,
                        "status_code": 200 if success else 503,
                        "duration_ms": 42 if success else 93,
                        "error_message": "" if success else "HTTP 503 (演示记录)",
                    },
                )

        summarize_daily_health(yesterday.isoformat())
        self.stdout.write(self.style.SUCCESS("演示环境、团队、服务及昨日统计已准备好。"))
