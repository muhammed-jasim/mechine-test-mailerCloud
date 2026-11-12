import logging
import redis
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, F
from django.db.models.functions import TruncHour
from django.utils import timezone

from .models import Submission, HourlyAggregation

logger = logging.getLogger(__name__)

WATERMARK_KEY = 'celery_aggregator_last_processed_id'


def get_redis_client():
    return redis.Redis.from_url(settings.CELERY_BROKER_URL)


@shared_task(bind=True, acks_late=True, max_retries=3)
def aggregate_hourly_submissions(self):
    """
    Celery Beat periodic task (runs every 5 seconds).
    Pulls newly arrived submissions since the last watermark using Django ORM,
    aggregates them into 1-hour tumbling buckets via TruncHour,
    and updates HourlyAggregation in PostgreSQL.
    """
    r = get_redis_client()
    raw_val = r.get(WATERMARK_KEY)
    last_id = int(raw_val) if raw_val is not None else None

    # 1. Fetch current max submission ID via Django ORM
    current_max_id = Submission.objects.aggregate(max_id=Max('id'))['max_id'] or 0

    # If no watermark in Redis yet, check if database already has aggregations
    if last_id is None:
        if HourlyAggregation.objects.exists():
            last_id = current_max_id
            r.set(WATERMARK_KEY, last_id)
            logger.info(f"Initialized Celery Beat watermark at existing max ID: {last_id}")
            return f"Initialized watermark to {last_id}"
        else:
            last_id = 0

    # If no new submissions arrived, nothing to aggregate
    if current_max_id <= last_id:
        return f"No new submissions (up to ID {last_id})"

    # 2. Query newly arrived submissions grouped by form_id and hour bucket using Django ORM
    batch_aggregations = (
        Submission.objects
        .filter(id__gt=last_id, id__lte=current_max_id)
        .annotate(hour_bucket=TruncHour('created_at'))
        .values('form_id', 'hour_bucket')
        .annotate(batch_count=Count('id'))
    )

    # 3. Update HourlyAggregation table atomically using Django ORM
    with transaction.atomic():
        for item in batch_aggregations:
            form_id = item['form_id']
            hour_bucket = item['hour_bucket']
            batch_count = item['batch_count']

            obj, created = HourlyAggregation.objects.get_or_create(
                form_id=form_id,
                hour_bucket=hour_bucket,
                defaults={'count': batch_count}
            )
            if not created:
                HourlyAggregation.objects.filter(pk=obj.pk).update(
                    count=F('count') + batch_count,
                    last_updated=timezone.now()
                )

    # 4. Advance watermark in Redis only after database transaction commits
    r.set(WATERMARK_KEY, current_max_id)
    msg = f"Celery Beat aggregated submissions from ID {last_id} to {current_max_id}"
    logger.info(msg)
    return msg


def resync_all_aggregations():
    """
    Recalculates all hourly aggregations from scratch using Django ORM.
    Useful for initialization or resetting state.
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

    r = get_redis_client()
    r.set(WATERMARK_KEY, current_max_id)
    return current_max_id
