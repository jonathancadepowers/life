from django.urls import path
from . import views

app_name = "waist_measurements"

urlpatterns = [
    path("waist_measurements/log_measurement", views.log_measurement, name="log_measurement"),
]
