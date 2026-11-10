from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Prefixed API routes: /api/...
    path('api/', include('submissions.urls')),
    # Root routes compatibility: /submissions/ and /forms/<form_id>/submissions/
    path('', include('submissions.urls')),
]
