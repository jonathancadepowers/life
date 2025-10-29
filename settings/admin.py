from django.contrib import admin
from .models import Setting


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
