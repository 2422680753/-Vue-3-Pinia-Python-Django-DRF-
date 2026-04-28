from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/exam/monitoring/(?P<attempt_id>\d+)/$', consumers.ExamMonitoringConsumer.as_asgi()),
]
