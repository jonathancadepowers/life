from django.contrib import admin
from .models import NutritionEntry


@admin.register(NutritionEntry)
class NutritionEntryAdmin(admin.ModelAdmin):
    list_display = ['consumption_date', 'source', 'calories', 'protein', 'carbs', 'fat', 'created_at']
    list_filter = ['source', 'consumption_date']
    search_fields = ['source_id']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'consumption_date'

    fieldsets = (
        ('Source Information', {
            'fields': ('source', 'source_id')
        }),
        ('Nutrition Details', {
            'fields': ('consumption_date', 'calories', 'protein', 'carbs', 'fat')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
