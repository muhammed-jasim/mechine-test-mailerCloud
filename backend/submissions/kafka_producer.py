import json
import logging
import time
from django.conf import settings

logger = logging.getLogger(__name__)

_producer = None
_last_connection_attempt = 0
_RETRY_INTERVAL = 10.0  # Seconds before retrying Kafka connection if offline


def get_kafka_producer():
    """
    Lazy singleton KafkaProducer initialization with backoff.
    """
    global _producer, _last_connection_attempt
    if _producer is not None:
        return _producer

    now = time.time()
    if now - _last_connection_attempt < _RETRY_INTERVAL:
        return None

    _last_connection_attempt = now
    try:
        from kafka import KafkaProducer
        _producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            request_timeout_ms=1000,
            max_block_ms=1000,
            retries=1,
        )
        logger.info(f"Connected to Kafka at {settings.KAFKA_BOOTSTRAP_SERVERS}")
    except Exception as e:
        logger.warning(f"Kafka unavailable ({e}). Retrying in {_RETRY_INTERVAL}s. API continues normally.")
        _producer = None

    return _producer


def publish_submission_event(submission):
    """
    Publish a submission event to Kafka only for newly created submissions.
    Topic: submission-events
    """
    producer = get_kafka_producer()
    if producer is None:
        return False

    payload = {
        'id': submission.id,
        'form_id': submission.form_id,
        'idempotency_key': submission.idempotency_key,
        'email': submission.email,
        'data': submission.data,
        'created_at': submission.created_at.isoformat(),
    }

    try:
        topic = getattr(settings, 'KAFKA_TOPIC_SUBMISSIONS', 'submission-events')
        producer.send(
            topic,
            key=submission.form_id,
            value=payload
        )
        return True
    except Exception as exc:
        logger.error(f"Failed to publish submission {submission.id} to Kafka: {exc}")
        return False
