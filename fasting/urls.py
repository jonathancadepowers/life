from django.urls import path
from . import views

app_name = 'fasting'

urlpatterns = [
    path('activity-logger/', views.activity_logger, name='activity_logger'),
    path('api/log-fast/', views.log_fast, name='log_fast'),
]
