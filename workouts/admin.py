from django.contrib import admin
from .models import Workout


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = (
        'start',
        'source',
        'sport_id',
        'duration_display',
        'average_heart_rate',
        'max_heart_rate',
        'calories_burned',
    )
    list_filter = ('source', 'sport_id', 'start')
    search_fields = ('source', 'source_id', 'sport_id')
    readonly_fields = ('created_at', 'updated_at', 'duration_display')
    date_hierarchy = 'start'

    fieldsets = (
        ('Source Information', {
            'fields': ('source', 'source_id')
        }),
        ('Workout Details', {
            'fields': (
                'start',
                'end',
                'timezone_offset',
                'sport_id',
            )
        }),
        ('Metrics', {
            'fields': (
                'average_heart_rate',
                'max_heart_rate',
                'calories_burned',
            )
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def duration_display(self, obj):
        """Display workout duration in readable format"""
        duration = obj.duration
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    duration_display.short_description = 'Duration'
