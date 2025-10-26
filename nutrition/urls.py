from django.urls import path
from . import views

app_name = 'nutrition'

urlpatterns = [
    path('api/log-nutrition/', views.log_nutrition, name='log_nutrition'),
]
