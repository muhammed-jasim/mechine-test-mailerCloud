from rest_framework import serializers
from .models import Submission, HourlyAggregation, DuplicateLog


class SubmissionCreateSerializer(serializers.Serializer):
    form_id = serializers.CharField(
        max_length=128,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'required': 'form_id is required.',
            'blank': 'form_id cannot be blank.',
        }
    )
    idempotency_key = serializers.CharField(
        max_length=255,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'required': 'idempotency_key is required.',
            'blank': 'idempotency_key cannot be blank.',
        }
    )
    email = serializers.EmailField(
        max_length=255,
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'email is required.',
            'invalid': 'Enter a valid email address.',
            'blank': 'email cannot be blank.',
        }
    )
    data = serializers.DictField(
        required=False,
        default=dict
    )

    def validate_form_id(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("form_id cannot be empty.")
        return cleaned

    def validate_idempotency_key(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("idempotency_key cannot be empty.")
        return cleaned


class SubmissionDetailSerializer(serializers.ModelSerializer):
    is_duplicate = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Submission
        fields = [
            'id',
            'form_id',
            'idempotency_key',
            'email',
            'data',
            'created_at',
            'is_duplicate',
        ]


class HourlyAggregationSerializer(serializers.ModelSerializer):
    class Meta:
        model = HourlyAggregation
        fields = ['id', 'form_id', 'hour_bucket', 'count', 'last_updated']


class DuplicateLogSerializer(serializers.ModelSerializer):
    original_submission_id = serializers.IntegerField(source='original_submission.id', read_only=True)

    class Meta:
        model = DuplicateLog
        fields = [
            'id',
            'original_submission_id',
            'form_id',
            'idempotency_key',
            'attempted_email',
            'attempted_data',
            'detected_at',
        ]
