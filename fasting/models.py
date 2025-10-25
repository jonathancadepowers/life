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
    duration = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Fasting duration in hours"
    )
    fast_end_date = models.DateTimeField(
        help_text="When the fast ended (UTC)"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fast_end_date']
        unique_together = ['source', 'source_id']
        indexes = [
            models.Index(fields=['-fast_end_date']),
            models.Index(fields=['source', 'source_id']),
        ]
        verbose_name = 'Fasting Session'
        verbose_name_plural = 'Fasting Sessions'

    def __str__(self):
        return f"{self.source} fast: {self.duration}h on {self.fast_end_date.strftime('%Y-%m-%d')}"
