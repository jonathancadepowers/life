from django.contrib import admin
from .models import Goal


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["goal_id", "display_string", "created_at", "updated_at"]
    search_fields = ["display_string"]
    readonly_fields = ["goal_id", "created_at", "updated_at"]

    fieldsets = (
        ("Goal Information", {"fields": ("goal_id", "display_string")}),
        ("Audit Information", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
