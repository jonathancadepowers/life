from django.contrib import admin
from .models import MonthlyObjective


@admin.register(MonthlyObjective)
class MonthlyObjectiveAdmin(admin.ModelAdmin):
    list_display = ['objective_id', 'label', 'start', 'end', 'objective_value', 'result', 'created_at']
    list_filter = ['start', 'end']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start'

    fieldsets = (
        ('Objective Details', {
            'fields': ('objective_id', 'label', 'objective_value')
        }),
        ('Date Range', {
            'fields': ('start', 'end', 'timezone'),
            'description': 'Must span a full calendar month (first day to last day). Timezone determines how dates are interpreted.'
        }),
        ('SQL Definition', {
            'fields': ('objective_definition',)
        }),
        ('Result', {
            'fields': ('result',),
            'description': 'Actual result from executing the SQL query. Will be populated automatically.'
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
