from django.contrib import admin
from .models import WeighIn


@admin.register(WeighIn)
class WeighInAdmin(admin.ModelAdmin):
    list_display = (
        "measurement_time",
        "weight",
        "source",
        "source_id",
    )
    list_filter = ("source", "measurement_time")
    search_fields = ("source", "source_id")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "measurement_time"

    fieldsets = (
        ("Source Information", {"fields": ("source", "source_id")}),
        (
            "Measurement",
            {
                "fields": (
                    "measurement_time",
                    "weight",
                )
            },
        ),
        ("Audit Information", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
