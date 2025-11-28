from django.contrib import admin
from .models import Inspiration


@admin.register(Inspiration)
class InspirationAdmin(admin.ModelAdmin):
    list_display = ['type', 'flip_text_preview', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['flip_text', 'type']
    ordering = ['-created_at']

    fieldsets = (
        ('Content', {
            'fields': ('image', 'flip_text', 'type')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_at', 'updated_at']

    def flip_text_preview(self, obj):
        """Show truncated flip text in list view"""
        return obj.flip_text[:60] + '...' if len(obj.flip_text) > 60 else obj.flip_text
    flip_text_preview.short_description = 'Flip Text'
