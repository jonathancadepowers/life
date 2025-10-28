from django.contrib import admin
from .models import Target, DailyAgenda


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ['target_id', 'target_name', 'goal_id', 'created_at', 'updated_at']
    list_filter = ['goal_id', 'created_at']
    search_fields = ['target_id', 'target_name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Target Information', {
            'fields': ('target_id', 'target_name', 'goal_id')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DailyAgenda)
class DailyAgendaAdmin(admin.ModelAdmin):
    list_display = ['date', 'target_1', 'target_1_score', 'target_2', 'target_2_score', 'target_3', 'target_3_score', 'day_score', 'created_at']
    list_filter = ['date']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'

    fieldsets = (
        ('Date', {
            'fields': ('date',)
        }),
        ('Target 1', {
            'fields': ('project_1', 'goal_1', 'target_1', 'target_1_score')
        }),
        ('Target 2', {
            'fields': ('project_2', 'goal_2', 'target_2', 'target_2_score')
        }),
        ('Target 3', {
            'fields': ('project_3', 'goal_3', 'target_3', 'target_3_score')
        }),
        ('Overall Score', {
            'fields': ('day_score',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
