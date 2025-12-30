from django.urls import path
from . import views

app_name = 'youtube_avoidance'

urlpatterns = [
    path('youtube_avoidance/log_youtube', views.log_youtube, name='log_youtube'),
]
