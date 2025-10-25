from django.db import models


class Goal(models.Model):
    """
    Represents a goal that can be associated with time logs.
    """
    goal_id = models.AutoField(
        primary_key=True,
        help_text="Unique goal identifier"
    )
    display_string = models.CharField(
        max_length=255,
        help_text="Human-readable goal name"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_string']
        verbose_name = 'Goal'
        verbose_name_plural = 'Goals'

    def __str__(self):
        return self.display_string
