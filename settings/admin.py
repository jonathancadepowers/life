from django.contrib import admin
from .models import Setting, LifeTrackerColumn


@admin.register(LifeTrackerColumn)
class LifeTrackerColumnAdmin(admin.ModelAdmin):
    list_display = ['column_name', 'display_name', 'order', 'enabled', 'updated_at']
    list_filter = ['enabled']
    search_fields = ['column_name', 'display_name', 'tooltip_text']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['order', 'enabled']
    ordering = ['order', 'column_name']

    fieldsets = (
        ('Column Information', {
            'fields': ('column_name', 'display_name', 'tooltip_text', 'order', 'enabled')
        }),
        ('SQL Query', {
            'fields': ('sql_query',),
            'description': 'SQL query to determine if checkbox should appear. Available parameters: :day_start, :day_end'
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


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
