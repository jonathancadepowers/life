from django.db import models


class MonthlyObjective(models.Model):
    """
    Represents a monthly objective with a SQL-based definition.
    Each objective applies to a specific calendar month.
    """
    start = models.DateField(
        help_text="First day of the month for this objective",
        db_index=True
    )
    end = models.DateField(
        help_text="Last day of the month for this objective",
        db_index=True
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

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start', 'label']
        verbose_name = 'Monthly Objective'
        verbose_name_plural = 'Monthly Objectives'

    def __str__(self):
        return f"{self.label} ({self.start.strftime('%B %Y')})"
