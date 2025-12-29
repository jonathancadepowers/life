from django.contrib import admin
from .models import Setting, LifeTrackerColumn


@admin.register(LifeTrackerColumn)
class LifeTrackerColumnAdmin(admin.ModelAdmin):
    list_display = ['id', 'column_name', 'display_name', 'icon', 'parent', 'start_date', 'end_date', 'is_active_status']
    list_filter = []
    search_fields = ['id', 'column_name', 'display_name', 'tooltip_text']
    readonly_fields = ['id', 'created_at', 'updated_at', 'is_active_status']
    ordering = ['id']

    fieldsets = (
        ('Column Information', {
            'fields': ('id', 'column_name', 'display_name', 'icon', 'parent', 'tooltip_text')
        }),
        ('Active Period', {
            'fields': ('start_date', 'end_date', 'is_active_status'),
            'description': 'Define when this habit is active. End date can be a date (YYYY-MM-DD) or "ongoing".'
        }),
        ('SQL Query', {
            'fields': ('sql_query', 'details_display'),
            'description': 'SQL query to determine if checkbox should appear. Available parameters: :day_start, :day_end'
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_active_status(self, obj):
        """Show if this habit is currently active"""
        from datetime import date
        if obj.is_active_on(date.today()):
            return "✓ Active"
        return "✗ Inactive"
    is_active_status.short_description = 'Current Status'


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_preview', 'updated_at']
    search_fields = ['key', 'value', 'description']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Setting Information', {
            'fields': ('key', 'value', 'description')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def value_preview(self, obj):
        """Show a preview of the value (truncated if long)"""
        if len(obj.value) > 50:
            return f"{obj.value[:50]}..."
        return obj.value
    value_preview.short_description = 'Value'
