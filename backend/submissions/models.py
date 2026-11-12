from django.db import models


class Submission(models.Model):
    """
    Stores form submissions with an idempotency key unique constraint
    to strictly prevent duplicates.
    """
    form_id = models.CharField(max_length=128, db_index=True)
    idempotency_key = models.CharField(max_length=255, unique=True, db_index=True)
    email = models.EmailField(max_length=255, db_index=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['form_id', 'created_at']),
        ]

    def __str__(self):
        return f"{self.form_id} - {self.email} ({self.idempotency_key})"


class HourlyAggregation(models.Model):
    """
    Stores aggregated submission counts per form and hour bucket,
    updated in real-time by Apache Flink or the aggregation pipeline.
    """
    form_id = models.CharField(max_length=128, db_index=True)
    hour_bucket = models.DateTimeField(db_index=True)
    count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-hour_bucket', 'form_id']
        constraints = [
            models.UniqueConstraint(
                fields=['form_id', 'hour_bucket'],
                name='unique_form_hour_aggregation'
            )
        ]

    def __str__(self):
        return f"{self.form_id} @ {self.hour_bucket}: {self.count}"


class DuplicateLog(models.Model):
    """
    Audit log that records every duplicate idempotency key attempt
    intercepted by the system.
    """
    original_submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='duplicate_logs',
        null=True,
        blank=True
    )
    form_id = models.CharField(max_length=128, db_index=True)
    idempotency_key = models.CharField(max_length=255, db_index=True)
    attempted_email = models.EmailField(max_length=255)
    attempted_data = models.JSONField(default=dict, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['form_id', 'detected_at']),
            models.Index(fields=['idempotency_key']),
        ]

    def __str__(self):
        return f"Duplicate [{self.idempotency_key}] on form '{self.form_id}' at {self.detected_at}"


class AggregationWatermark(models.Model):
    """
    Persists the stream processing watermark inside PostgreSQL
    in the same ACID transaction as the aggregation counts.
    Ensures crash recovery without double-counting or state desync.
    """
    key = models.CharField(max_length=64, unique=True, default='submission_aggregation')
    last_processed_id = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Watermark [{self.key}]: {self.last_processed_id}"
