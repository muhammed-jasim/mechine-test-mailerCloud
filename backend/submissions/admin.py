from django.contrib import admin
from .models import Submission, HourlyAggregation


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
