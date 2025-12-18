from django.contrib import admin
from .models import WaistMeasurement


@admin.register(WaistMeasurement)
class WaistMeasurementAdmin(admin.ModelAdmin):
    list_display = ['measurement_time', 'waist_circumference', 'source', 'created_at']
    list_filter = ['source', 'measurement_time']
    search_fields = ['source']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'measurement_time'

    fieldsets = (
        ('Measurement Data', {
            'fields': ('measurement_time', 'waist_circumference', 'source')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
