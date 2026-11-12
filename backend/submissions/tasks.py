import logging
from datetime import timedelta
from celery import shared_task
from django.db import transaction
from django.db.models import Count, Max
from django.db.models.functions import TruncHour

from .models import Submission, HourlyAggregation, AggregationWatermark

logger = logging.getLogger(__name__)

WATERMARK_KEY = 'submission_aggregation'


@shared_task(bind=True, acks_late=True, max_retries=3)
def aggregate_hourly_submissions(self):
    """
    Celery Beat periodic task.
    ACID-compliant incremental hourly aggregation with crash recovery:
    1. Locks the AggregationWatermark row with select_for_update() inside an atomic transaction.
    2. Identifies all newly arrived submissions (id > watermark.last_processed_id AND id <= current_max_id).
    3. Finds distinct (form_id, hour_bucket) pairs touched by new records.
    4. Computes the authoritative count for each touched bucket and upserts into HourlyAggregation.
    5. Updates the watermark row inside the EXACT SAME atomic transaction.

    Crash Recovery Guarantees:
    - Zero double-counting: even if the task retries or crashes mid-way, authoritative counts are set.
    - Zero state desync: watermark and counts commit together atomically in PostgreSQL.
    - No Redis dependency for state: Redis is only used as a task message transport.
    """
    with transaction.atomic():
        watermark, _ = AggregationWatermark.objects.select_for_update().get_or_create(
            key=WATERMARK_KEY,
            defaults={'last_processed_id': 0}
        )
        last_id = watermark.last_processed_id

        # 1. Fetch current max submission ID
        current_max_id = Submission.objects.aggregate(max_id=Max('id'))['max_id'] or 0

        # If no new submissions arrived, nothing to do
        if current_max_id <= last_id:
            return f"No new submissions (up to ID {last_id})"

        # 2. Find which (form_id, hour_bucket) pairs are touched by new submissions.
        # Note: .order_by() clears default model ordering so distinct() operates strictly on (form_id, hour_bucket).
        touched_buckets = (
            Submission.objects
            .filter(id__gt=last_id, id__lte=current_max_id)
            .annotate(hour_bucket=TruncHour('created_at'))
            .values('form_id', 'hour_bucket')
            .order_by()
            .distinct()
        )

        # 3. For each touched bucket, compute authoritative count and upsert
        updated_count = 0
        for item in touched_buckets:
            form_id = item['form_id']
            hour_bucket = item['hour_bucket']

            # Authoritative total for this bucket up to current_max_id
            authoritative_count = Submission.objects.filter(
                form_id=form_id,
                created_at__gte=hour_bucket,
                created_at__lt=hour_bucket + timedelta(hours=1),
                id__lte=current_max_id
            ).count()

            HourlyAggregation.objects.update_or_create(
                form_id=form_id,
                hour_bucket=hour_bucket,
                defaults={'count': authoritative_count}
            )
            updated_count += 1

        # 4. Advance watermark inside the SAME atomic transaction
        watermark.last_processed_id = current_max_id
        watermark.save()

    msg = f"Celery Beat updated {updated_count} bucket(s) from ID {last_id} to {current_max_id}"
    logger.info(msg)
    return msg


def resync_all_aggregations():
    """
    Recalculates all hourly aggregations from scratch using Django ORM.
    Resets the PostgreSQL watermark in the same transaction.
    """
    with transaction.atomic():
        HourlyAggregation.objects.all().delete()

        all_aggregations = (
            Submission.objects
            .annotate(hour_bucket=TruncHour('created_at'))
            .values('form_id', 'hour_bucket')
            .annotate(total_count=Count('id'))
        )

        records = [
            HourlyAggregation(
                form_id=item['form_id'],
                hour_bucket=item['hour_bucket'],
                count=item['total_count']
            )
            for item in all_aggregations
        ]
        HourlyAggregation.objects.bulk_create(records, batch_size=2000)

        current_max_id = Submission.objects.aggregate(max_id=Max('id'))['max_id'] or 0

        watermark, _ = AggregationWatermark.objects.select_for_update().get_or_create(
            key=WATERMARK_KEY,
            defaults={'last_processed_id': 0}
        )
        watermark.last_processed_id = current_max_id
        watermark.save()

    return current_max_id
