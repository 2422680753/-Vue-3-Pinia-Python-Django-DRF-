from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/video/progress/(?P<lesson_id>\d+)/$', consumers.VideoProgressConsumer.as_asgi()),
]
