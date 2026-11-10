from django.contrib import admin
from .models import Submission, HourlyAggregation, DuplicateLog


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'form_id', 'email', 'idempotency_key', 'created_at')
    search_fields = ('form_id', 'email', 'idempotency_key')
    list_filter = ('form_id', 'created_at')


@admin.register(HourlyAggregation)
class HourlyAggregationAdmin(admin.ModelAdmin):
    list_display = ('id', 'form_id', 'hour_bucket', 'count', 'last_updated')
    search_fields = ('form_id',)
    list_filter = ('form_id', 'hour_bucket')


@admin.register(DuplicateLog)
class DuplicateLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'form_id', 'idempotency_key', 'attempted_email', 'detected_at')
    search_fields = ('form_id', 'idempotency_key', 'attempted_email')
    list_filter = ('form_id', 'detected_at')
