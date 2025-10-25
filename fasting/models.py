from django.db import models


class FastingSession(models.Model):
    """
    Represents a fasting session from various sources (Zero app, Manual, etc.)
    """
    source = models.CharField(
        max_length=50,
        help_text="Source of the fasting data (e.g., 'Zero', 'Manual')"
    )
    source_id = models.CharField(
        max_length=255,
        help_text="ID from the external source system",
        db_index=True
    )
    start = models.DateTimeField(
        help_text="Fasting start time"
    )
    end = models.DateTimeField(
        help_text="Fasting end time",
        null=True,
        blank=True
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start']
        unique_together = ['source', 'source_id']
        indexes = [
            models.Index(fields=['-start']),
            models.Index(fields=['source', 'source_id']),
        ]
        verbose_name = 'Fasting Session'
        verbose_name_plural = 'Fasting Sessions'

    def __str__(self):
        return f"{self.source} fast on {self.start.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration(self):
        """Calculate fasting duration"""
        if self.end:
            return self.end - self.start
        return None

    @property
    def duration_hours(self):
        """Calculate fasting duration in hours"""
        if self.duration:
            return self.duration.total_seconds() / 3600
        return None
