from django.contrib import admin
from .models import Workout
from .sport_ids import get_sport_name


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = (
        'start',
        'source',
        'sport_name_display',
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

    def sport_name_display(self, obj):
        """Display human-readable sport name"""
        return get_sport_name(obj.sport_id)
    sport_name_display.short_description = 'Sport'
    sport_name_display.admin_order_field = 'sport_id'

    def duration_display(self, obj):
        """Display workout duration in readable format"""
        duration = obj.duration
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    duration_display.short_description = 'Duration'
