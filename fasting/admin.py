from django.contrib import admin
from .models import FastingSession


@admin.register(FastingSession)
class FastingSessionAdmin(admin.ModelAdmin):
    list_display = [
        'start',
        'end',
        'duration_display',
        'source'
    ]
    list_filter = ['source']
    search_fields = ['source_id']
    date_hierarchy = 'start'
    readonly_fields = ['created_at', 'updated_at', 'duration_display', 'duration_hours']

    fieldsets = (
        ('Fasting Details', {
            'fields': ('start', 'end')
        }),
        ('Source Information', {
            'fields': ('source', 'source_id')
        }),
        ('Calculated Fields', {
            'fields': ('duration_display', 'duration_hours'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def duration_display(self, obj):
        """Display duration in human-readable format"""
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        return "-"
    duration_display.short_description = 'Duration'
