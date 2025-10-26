from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['project_id', 'display_string', 'created_at', 'updated_at']
    search_fields = ['display_string']
    readonly_fields = ['project_id', 'created_at', 'updated_at']

    fieldsets = (
        ('Project Information', {
            'fields': ('project_id', 'display_string')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
