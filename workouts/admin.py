from django.contrib import admin
from .models import Workout


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = (
        'start',
        'end',
        'source',
        'sport_id',
        'average_heart_rate',
        'max_heart_rate',
        'calories_burned',
    )
    list_filter = ('source', 'sport_id', 'start')
    search_fields = ('source', 'source_id', 'sport_id')
    readonly_fields = ('created_at', 'updated_at')
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
