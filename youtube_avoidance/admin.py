from django.contrib import admin
from .models import YouTubeAvoidanceLog


@admin.register(YouTubeAvoidanceLog)
class YouTubeAvoidanceLogAdmin(admin.ModelAdmin):
    list_display = ['log_date', 'source', 'source_id', 'created_at']
    list_filter = ['source', 'log_date']
    search_fields = ['source', 'source_id']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-log_date']

    fieldsets = (
        ('Log Information', {
            'fields': ('source', 'source_id', 'log_date')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
