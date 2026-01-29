from django.contrib import admin
from .models import ToDo


@admin.register(ToDo)
class ToDoAdmin(admin.ModelAdmin):
    list_display = ['title', 'critical', 'created_at']
    list_filter = ['critical']
    search_fields = ['title', 'details']
