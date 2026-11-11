from datetime import timedelta
from django.db import IntegrityError, transaction
from django.db.models import Count, Min, Max
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import Submission, HourlyAggregation, DuplicateLog
from .serializers import (
    SubmissionCreateSerializer,
    SubmissionDetailSerializer,
    HourlyAggregationSerializer,
    DuplicateLogSerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class SubmissionCreateListView(APIView):
    """
    POST /api/submissions/
    Create a new submission or return existing if duplicate idempotency_key.
    Logs every intercepted duplicate to the DuplicateLog table.
    Publishes to Kafka ONLY on new creation.

    GET /api/submissions/
    List all submissions with pagination (10 per page).
    """

    def post(self, request, *args, **kwargs):
        serializer = SubmissionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        idempotency_key = validated_data['idempotency_key']
        form_id = validated_data['form_id']
        email = validated_data['email']
        payload_data = validated_data.get('data', {})

        is_duplicate = False
        try:
            # Atomic creation with savepoint leveraging DB unique constraint on idempotency_key
            with transaction.atomic():
                submission = Submission.objects.create(
                    idempotency_key=idempotency_key,
                    form_id=form_id,
                    email=email,
                    data=payload_data,
                )
            response_status = status.HTTP_201_CREATED
        except IntegrityError:
            # Duplicate idempotency_key detected: fetch existing record
            submission = Submission.objects.get(idempotency_key=idempotency_key)
            is_duplicate = True
            response_status = status.HTTP_200_OK

            # Log the duplicate attempt to DuplicateLog audit table
            try:
                DuplicateLog.objects.create(
                    original_submission=submission,
                    form_id=form_id,
                    idempotency_key=idempotency_key,
                    attempted_email=email,
                    attempted_data=payload_data,
                )
            except Exception:
                pass

        response_data = SubmissionDetailSerializer(submission).data
        response_data['is_duplicate'] = is_duplicate
        return Response(response_data, status=response_status)

    def get(self, request, *args, **kwargs):
        queryset = Submission.objects.all().order_by('-created_at')
        form_id = request.query_params.get('form_id')
        if form_id:
            queryset = queryset.filter(form_id=form_id)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = SubmissionDetailSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class FormSubmissionsListView(APIView):
    """
    GET /api/forms/{form_id}/submissions/
    Returns submissions for the selected form with 10 records per page.
    """
    def get(self, request, form_id, *args, **kwargs):
        queryset = Submission.objects.filter(form_id=form_id).order_by('-created_at')
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = SubmissionDetailSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class FormSummaryListView(APIView):
    """
    GET /api/forms/
    Lists distinct form IDs with submission count and last submission date.
    """
    def get(self, request, *args, **kwargs):
        forms = (
            Submission.objects.values('form_id')
            .annotate(
                submission_count=Count('id'),
                last_submission=Max('created_at'),
                first_submission=Min('created_at')
            )
            .order_by('-submission_count')
        )
        return Response(list(forms), status=status.HTTP_200_OK)


class DuplicateLogListView(APIView):
    """
    GET /api/duplicates/
    Returns paginated audit log of duplicate idempotency key attempts.
    """
    def get(self, request, *args, **kwargs):
        queryset = DuplicateLog.objects.all().order_by('-detected_at')
        form_id = request.query_params.get('form_id')
        if form_id:
            queryset = queryset.filter(form_id=form_id)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = DuplicateLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AnalyticsOverviewView(APIView):
    """
    GET /api/analytics/overview/
    Overview metrics for the dashboard including duplicate logs.
    """
    def get(self, request, *args, **kwargs):
        now = timezone.now()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_submissions = Submission.objects.count()
        total_forms = Submission.objects.values('form_id').distinct().count()
        today_submissions = Submission.objects.filter(created_at__gte=start_of_today).count()
        total_duplicates = DuplicateLog.objects.count()

        # Form distribution
        form_distribution = list(
            Submission.objects.values('form_id')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # Recent submissions
        recent_qs = Submission.objects.all().order_by('-created_at')[:5]
        recent_submissions = SubmissionDetailSerializer(recent_qs, many=True).data

        # Recent duplicate logs
        recent_duplicates_qs = DuplicateLog.objects.all().order_by('-detected_at')[:8]
        recent_duplicates = DuplicateLogSerializer(recent_duplicates_qs, many=True).data

        # Hourly chart (last 24 hours)
        past_24h = now - timedelta(hours=24)
        aggregations = HourlyAggregation.objects.filter(hour_bucket__gte=past_24h).order_by('hour_bucket')

        hourly_data = []
        if aggregations.exists():
            hourly_map = {}
            for item in aggregations:
                key = item.hour_bucket.strftime('%Y-%m-%d %H:00')
                hourly_map[key] = hourly_map.get(key, 0) + item.count
            hourly_data = [{'hour': k, 'count': v} for k, v in hourly_map.items()]
        else:
            submissions_24h = Submission.objects.filter(created_at__gte=past_24h)
            hourly_map = {}
            for sub in submissions_24h:
                bucket = sub.created_at.replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:00')
                hourly_map[bucket] = hourly_map.get(bucket, 0) + 1
            hourly_data = [{'hour': k, 'count': v} for k, v in sorted(hourly_map.items())]

        return Response({
            'total_submissions': total_submissions,
            'total_forms': total_forms,
            'today_submissions': today_submissions,
            'total_duplicates': total_duplicates,
            'form_distribution': form_distribution,
            'hourly_chart': hourly_data,
            'recent_submissions': recent_submissions,
            'recent_duplicates': recent_duplicates,
        }, status=status.HTTP_200_OK)


class HourlyAggregationListView(APIView):
    """
    GET /api/analytics/hourly/
    Hourly submission statistics.
    """
    def get(self, request, *args, **kwargs):
        form_id = request.query_params.get('form_id')
        aggregations = HourlyAggregation.objects.all().order_by('-hour_bucket')
        if form_id:
            aggregations = aggregations.filter(form_id=form_id)

        serializer = HourlyAggregationSerializer(aggregations[:100], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
