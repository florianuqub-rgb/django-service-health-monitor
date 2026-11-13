import secrets

from django.db import models
from django.utils import timezone

from .crypto import decrypt_token, encrypt_token


class Environment(models.Model):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"
    CODE_CHOICES = [(DEV, "开发"), (TEST, "测试"), (PROD, "生产")]

    code = models.CharField(max_length=8, choices=CODE_CHOICES, unique=True)

    def __str__(self):
        return self.code


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Service(models.Model):
    name = models.CharField(max_length=100)
    base_url = models.URLField(max_length=500)
    health_path = models.CharField(max_length=200, default="/health")
    environment = models.ForeignKey(Environment, on_delete=models.PROTECT)
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    token_ciphertext = models.TextField(editable=False)
    token_rotated_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "environment"],
                name="unique_service_name_per_environment",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.environment.code})"

    def set_token(self, token):
        self.token_ciphertext = encrypt_token(token)
        self.token_rotated_at = timezone.now()

    def get_token(self):
        return decrypt_token(self.token_ciphertext)

    def save(self, *args, **kwargs):
        if not self.token_ciphertext:
            self.set_token(secrets.token_urlsafe(32))
        super().save(*args, **kwargs)


class CheckRecord(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="checks")
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)
    success = models.BooleanField()
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField()
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [models.Index(fields=["service", "checked_at"])]


class DailyStat(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="daily_stats")
    environment = models.ForeignKey(Environment, on_delete=models.PROTECT)
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    date = models.DateField()
    success_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    health_rate = models.FloatField(null=True, blank=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "service_id"]
        constraints = [
            models.UniqueConstraint(fields=["service", "date"], name="unique_daily_stat")
        ]

    def __str__(self):
        return f"{self.service_id}: {self.date}"
