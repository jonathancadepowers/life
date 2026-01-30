from django.contrib import admin
from .models import Task, TaskContext, TaskState


@admin.register(TaskContext)
class TaskContextAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'created_at']
    search_fields = ['name']


@admin.register(TaskState)
class TaskStateAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'is_terminal', 'created_at']
    list_filter = ['is_terminal']
    search_fields = ['name']
    ordering = ['order']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'state', 'critical', 'created_at']
    list_filter = ['critical', 'state']
    search_fields = ['title', 'details']
