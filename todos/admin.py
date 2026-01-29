from django.contrib import admin
from .models import Task, TaskContext


@admin.register(TaskContext)
class TaskContextAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'created_at']
    search_fields = ['name']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'context', 'critical', 'created_at']
    list_filter = ['critical', 'context']
    search_fields = ['title', 'details']
