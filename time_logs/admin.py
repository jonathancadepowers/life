from django.contrib import admin
from .models import TimeLog


@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = [
        "source",
        "source_id",
        "start",
        "end",
        "duration_display",
        "goals_display",
        "project_id",
        "created_at",
    ]
    list_filter = ["source", "project_id", "start"]
    search_fields = ["source_id", "source", "project_id"]
    readonly_fields = ["created_at", "updated_at", "duration_display"]
    date_hierarchy = "start"
    filter_horizontal = ["goals"]

    fieldsets = (
        ("Time Log Information", {"fields": ("source", "source_id", "start", "end", "duration_display")}),
        ("Associations", {"fields": ("goals", "project_id")}),
        ("Audit Information", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def duration_display(self, obj):
        """Display duration in a human-readable format."""
        hours = int(obj.duration_minutes // 60)
        minutes = int(obj.duration_minutes % 60)
        return f"{hours}h {minutes}m"

    duration_display.short_description = "Duration"  # type: ignore[attr-defined]

    def goals_display(self, obj):
        """Display associated goals as comma-separated list."""
        return ", ".join([goal.display_string for goal in obj.goals.all()]) or "None"

    goals_display.short_description = "Goals"  # type: ignore[attr-defined]
