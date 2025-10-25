from django.db import models


class TimeLog(models.Model):
    """
    Represents a time tracking entry for projects and goals.
    """
    timelog_id = models.AutoField(
        primary_key=True,
        help_text="Unique time log identifier"
    )
    source = models.CharField(
        max_length=50,
        default='Manual',
        help_text="Source of the time log data (e.g., 'Toggl', 'Manual')"
    )
    start = models.DateTimeField(
        help_text="When the time log started"
    )
    end = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the time log ended (null if still in progress)"
    )
    goal_id = models.IntegerField(
        blank=True,
        null=True,
        help_text="Associated goal ID"
    )
    project_id = models.IntegerField(
        blank=True,
        null=True,
        help_text="Associated project ID"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start']
        indexes = [
            models.Index(fields=['-start']),
            models.Index(fields=['goal_id']),
            models.Index(fields=['project_id']),
        ]
        verbose_name = 'Time Log'
        verbose_name_plural = 'Time Logs'

    def __str__(self):
        return f"Time log: {self.start.strftime('%Y-%m-%d %H:%M')} - {self.end.strftime('%Y-%m-%d %H:%M') if self.end else 'In Progress'}"

    @property
    def duration_minutes(self):
        """Calculate duration in minutes if end time is set."""
        if self.end:
            delta = self.end - self.start
            return delta.total_seconds() / 60
        return None
