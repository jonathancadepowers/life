from django.contrib import admin
from .models import TimeLog


@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = ['timelog_id', 'start', 'end', 'duration_display', 'goal_id', 'project_id', 'created_at']
    list_filter = ['goal_id', 'project_id', 'start']
    search_fields = ['timelog_id', 'goal_id', 'project_id']
    readonly_fields = ['timelog_id', 'created_at', 'updated_at', 'duration_display']
    date_hierarchy = 'start'

    fieldsets = (
        ('Time Log Information', {
            'fields': ('timelog_id', 'start', 'end', 'duration_display')
        }),
        ('Associations', {
            'fields': ('goal_id', 'project_id')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def duration_display(self, obj):
        """Display duration in a human-readable format."""
        if obj.duration_minutes is not None:
            hours = int(obj.duration_minutes // 60)
            minutes = int(obj.duration_minutes % 60)
            return f"{hours}h {minutes}m"
        return "In Progress"
    duration_display.short_description = 'Duration'
