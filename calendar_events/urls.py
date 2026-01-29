from django.urls import path
from . import views

app_name = 'calendar_events'

urlpatterns = [
    path('import/', views.webhook_import, name='webhook_import'),
    path('mailgun/', views.mailgun_webhook, name='mailgun_webhook'),
]
