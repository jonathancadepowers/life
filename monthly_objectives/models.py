from django.db import models


def get_default_timezone():
    """
    Get the default timezone for monthly objectives from settings.
    Falls back to 'America/Chicago' if setting doesn't exist.
    """
    from settings.models import Setting
    return Setting.get('default_timezone_for_monthly_objectives', 'America/Chicago')


class MonthlyObjective(models.Model):
    """
    Represents a monthly objective with a SQL-based definition.
    Each objective applies to a specific calendar month.
    """
    objective_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        null=True,  # Temporarily allow null for migration
        blank=True,
        help_text="Unique identifier for this objective"
    )
    start = models.DateField(
        help_text="First day of the month for this objective",
        db_index=True
    )
    end = models.DateField(
        help_text="Last day of the month for this objective",
        db_index=True
    )
    timezone = models.CharField(
        max_length=50,
        default=get_default_timezone,
        help_text="Timezone for date range (e.g., 'America/Chicago', 'America/New_York')"
    )
    label = models.CharField(
        max_length=255,
        help_text="Name/description of the objective (e.g., '30 Running Workouts')"
    )
    objective_value = models.FloatField(
        help_text="Target value for this objective (e.g., 30 for '30 running workouts')"
    )
    objective_definition = models.TextField(
        help_text="SQL query that defines how to measure this objective"
    )
    result = models.FloatField(
        null=True,
        blank=True,
        help_text="Actual result value from executing the objective_definition SQL query"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start', 'label']
        verbose_name = 'Monthly Objective'
        verbose_name_plural = 'Monthly Objectives'

    def __str__(self):
        return f"{self.label} ({self.start.strftime('%B %Y')})"
