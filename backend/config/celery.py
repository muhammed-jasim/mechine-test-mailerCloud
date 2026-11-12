import os
from celery import Celery

# Set default Django settings module for 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('form_analytics')

# Read config from Django settings with CELERY_ prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in installed apps (e.g. submissions/tasks.py).
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

