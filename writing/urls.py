from django.urls import path
from . import views

app_name = 'writing'

urlpatterns = [
    path('create_log', views.create_writing_log, name='create_log'),
]
