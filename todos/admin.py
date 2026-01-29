from django.contrib import admin
from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'critical', 'created_at']
    list_filter = ['critical']
    search_fields = ['title', 'details']
