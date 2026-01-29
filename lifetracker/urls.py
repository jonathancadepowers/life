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
    path("writing/", home_views.writing, name='writing'),
    path("contact/", home_views.contact, name='contact'),
    path("admin/", admin.site.urls),
    path("oauth/", include("oauth_integration.urls")),
    path("activity-report/", targets_views.activity_report, name='activity_report'),
    path("life-tracker/", targets_views.life_tracker, name='life_tracker'),
    path("settings/", settings_views.life_tracker_settings, name='life_tracker_settings'),
    path("settings/inspirations/add/", settings_views.add_inspiration, name='add_inspiration'),
    path("settings/inspirations/<int:inspiration_id>/edit/", settings_views.edit_inspiration, name='edit_inspiration'),
    path("settings/inspirations/<int:inspiration_id>/delete/", settings_views.delete_inspiration, name='delete_inspiration'),
    path("settings/writing-images/add/", settings_views.add_writing_image, name='add_writing_image'),
    path("settings/writing-images/<int:image_id>/edit/", settings_views.edit_writing_image, name='edit_writing_image'),
    path("settings/writing-images/<int:image_id>/delete/", settings_views.delete_writing_image, name='delete_writing_image'),
    path("settings/book-cover/upload/", settings_views.upload_book_cover, name='upload_book_cover'),
    path("settings/habits/add/", settings_views.add_habit, name='add_habit'),
    path("settings/habits/<str:column_name>/toggle-abandon/", settings_views.toggle_abandon_day, name='toggle_abandon_day'),
    path("settings/import/outlook-calendar/", settings_views.import_outlook_calendar, name='import_outlook_calendar'),
    path("targets/", include("targets.urls")),
    path("writing/", include("writing.urls")),
    path("", include("fasting.urls")),
    path("", include("nutrition.urls")),
    path("", include("youtube_avoidance.urls")),
    path("", include("waist_measurements.urls")),
    path("", home_views.home, name='home'),  # Catch-all for homepage, must be last
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
