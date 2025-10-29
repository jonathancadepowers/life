from django.db import models


class Goal(models.Model):
    """
    Represents a goal that can be associated with time logs.
    Maps to Toggl Tags.
    """
    goal_id = models.CharField(
        max_length=255,
        primary_key=True,
        help_text="Unique goal identifier (Toggl Tag ID)"
    )
    display_string = models.CharField(
        max_length=255,
        help_text="Human-readable goal name (Toggl Tag name)"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_string']
        verbose_name = 'Goal'
        verbose_name_plural = 'Goals'

    def __str__(self):
        return f"{self.display_string} (ID: {self.goal_id})"
