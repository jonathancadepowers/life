from django.contrib import admin
from .models import WritingLog


@admin.register(WritingLog)
class WritingLogAdmin(admin.ModelAdmin):
    list_display = ('log_date', 'source', 'source_id', 'created_at')
    list_filter = ('source', 'log_date')
    search_fields = ('source_id',)
    date_hierarchy = 'log_date'
    ordering = ('-log_date',)
