from django.urls import path
from . import views

app_name = 'youtube_avoidance'

urlpatterns = [
    path('api/log-youtube/', views.log_youtube, name='log_youtube'),
]
