from django.contrib import admin
from .models import Task, TaskState, TaskTag


@admin.register(TaskState)
class TaskStateAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'created_at']
    search_fields = ['name']
    ordering = ['order']


@admin.register(TaskTag)
class TaskTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'state', 'critical', 'created_at']
    list_filter = ['critical', 'state', 'tags']
    search_fields = ['title', 'details']
    filter_horizontal = ['tags']
