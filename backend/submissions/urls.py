from django.urls import path
from .views import (
    SubmissionCreateListView,
    FormSubmissionsListView,
    FormSummaryListView,
    AnalyticsOverviewView,
    HourlyAggregationListView,
)

urlpatterns = [
    # Primary required endpoints
    path('submissions/', SubmissionCreateListView.as_view(), name='submissions-create-list'),
    path('forms/<str:form_id>/submissions/', FormSubmissionsListView.as_view(), name='form-submissions-list'),

    # Analytics and Dashboard supporting endpoints
    path('forms/', FormSummaryListView.as_view(), name='forms-summary'),
    path('analytics/overview/', AnalyticsOverviewView.as_view(), name='analytics-overview'),
    path('analytics/hourly/', HourlyAggregationListView.as_view(), name='analytics-hourly'),
]

