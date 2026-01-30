from django.contrib import admin
from .models import Task, TaskState


@admin.register(TaskState)
class TaskStateAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'created_at']
    search_fields = ['name']
    ordering = ['order']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'state', 'critical', 'created_at']
    list_filter = ['critical', 'state']
    search_fields = ['title', 'details']
