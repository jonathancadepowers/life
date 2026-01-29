from django.contrib import admin
from .models import CalendarEvent


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ['subject', 'start', 'end', 'is_all_day', 'organizer', 'location']
    list_filter = ['is_all_day', 'organizer']
    search_fields = ['subject', 'location', 'organizer']
    date_hierarchy = 'start'
    ordering = ['-start']
    readonly_fields = ['outlook_id', 'created_at', 'updated_at']
