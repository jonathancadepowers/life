from django.contrib import admin
from .models import Task, TaskState, TaskTag, TimeBlock, TaskSchedule


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
    list_display = ['title', 'state', 'critical', 'calendar_start_time', 'calendar_end_time', 'created_at']
    list_filter = ['critical', 'state', 'tags']
    search_fields = ['title', 'details']
    filter_horizontal = ['tags']


@admin.register(TimeBlock)
class TimeBlockAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_time', 'end_time', 'created_at']
    search_fields = ['name']
    ordering = ['-start_time']


@admin.register(TaskSchedule)
class TaskScheduleAdmin(admin.ModelAdmin):
    list_display = ['task', 'start_time', 'end_time', 'created_at']
    list_filter = ['start_time']
    search_fields = ['task__title']
    ordering = ['-start_time']
    raw_id_fields = ['task']
