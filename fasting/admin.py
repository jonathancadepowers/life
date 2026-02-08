from django.contrib import admin
from .models import FastingSession


@admin.register(FastingSession)
class FastingSessionAdmin(admin.ModelAdmin):
    list_display = ["fast_end_date", "duration", "source", "source_id"]
    list_filter = ["source"]
    search_fields = ["source_id"]
    date_hierarchy = "fast_end_date"
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Fasting Details", {"fields": ("duration", "fast_end_date")}),
        ("Source Information", {"fields": ("source", "source_id")}),
        ("Audit Information", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
