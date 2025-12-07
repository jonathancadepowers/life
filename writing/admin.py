from django.contrib import admin
from .models import WritingLog, WritingPageImage


@admin.register(WritingPageImage)
class WritingPageImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'enabled', 'created_at')
    list_filter = ('enabled',)
    search_fields = ('title', 'excerpt')
    ordering = ('order', 'title')
    list_editable = ('order', 'enabled')

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'image', 'order', 'enabled')
        }),
        ('Excerpt', {
            'fields': ('excerpt',),
            'description': 'Novel excerpt that appears when clicking this image'
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at')


@admin.register(WritingLog)
class WritingLogAdmin(admin.ModelAdmin):
    list_display = ('log_date', 'source', 'source_id', 'created_at')
    list_filter = ('source', 'log_date')
    search_fields = ('source_id',)
    date_hierarchy = 'log_date'
    ordering = ('-log_date',)
