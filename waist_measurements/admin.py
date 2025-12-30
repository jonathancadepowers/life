from django.contrib import admin
from .models import WaistCircumferenceMeasurement


@admin.register(WaistCircumferenceMeasurement)
class WaistCircumferenceMeasurementAdmin(admin.ModelAdmin):
    list_display = ['log_date', 'measurement', 'source', 'source_id', 'created_at']
    list_filter = ['source', 'log_date']
    search_fields = ['source', 'source_id']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'log_date'

    fieldsets = (
        ('Measurement Data', {
            'fields': ('log_date', 'measurement', 'source', 'source_id')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
