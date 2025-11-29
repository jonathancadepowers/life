"""
URL configuration for lifetracker project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from targets import views as targets_views
from lifetracker import views as home_views
from settings import views as settings_views

urlpatterns = [
    path("about/", home_views.about, name='about'),
    path("inspirations/", home_views.inspirations, name='inspirations'),
    path("life-metrics/", home_views.life_metrics, name='life_metrics'),
    path("admin/", admin.site.urls),
    path("oauth/", include("oauth_integration.urls")),
    path("activity-report/", targets_views.activity_report, name='activity_report'),
    path("life-tracker/", targets_views.life_tracker, name='life_tracker'),
    path("settings/", settings_views.life_tracker_settings, name='life_tracker_settings'),
    path("settings/inspirations/add/", settings_views.add_inspiration, name='add_inspiration'),
    path("settings/inspirations/<int:inspiration_id>/edit/", settings_views.edit_inspiration, name='edit_inspiration'),
    path("settings/inspirations/<int:inspiration_id>/delete/", settings_views.delete_inspiration, name='delete_inspiration'),
    path("targets/", include("targets.urls")),
    path("writing/", include("writing.urls")),
    path("", include("fasting.urls")),
    path("", include("nutrition.urls")),
    path("", home_views.home, name='home'),  # Catch-all for homepage, must be last
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
