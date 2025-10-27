"""
URL configuration for OAuth integration views.
"""
from django.urls import path
from . import views

app_name = 'oauth_integration'

urlpatterns = [
    # Whoop OAuth flow
    path('whoop/authorize/', views.whoop_authorize, name='whoop_authorize'),
    path('whoop/callback/', views.whoop_callback, name='whoop_callback'),

    # Withings OAuth flow
    path('withings/authorize/', views.withings_authorize, name='withings_authorize'),
    path('withings/callback/', views.withings_callback, name='withings_callback'),
]
