from django.db import models


class WritingLog(models.Model):
    """
    Represents a writing log entry tracking days with at least 1.5 hours
    spent writing or thinking about writing.
    """
    source = models.CharField(
        max_length=50,
        help_text="Source of the writing log data (e.g., 'Manual', 'Toggl')"
    )
    source_id = models.CharField(
        max_length=255,
        help_text="ID from the external source system",
        db_index=True
    )
    log_date = models.DateField(
        help_text="Date of the writing session"
    )
    duration = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        help_text="Duration of writing session in hours",
        null=True,
        blank=True
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-log_date']
        unique_together = ['source', 'source_id']
        indexes = [
            models.Index(fields=['-log_date']),
            models.Index(fields=['source', 'source_id']),
        ]
        verbose_name = 'Writing Log'
        verbose_name_plural = 'Writing Logs'
        db_table = 'writing_logs'

    def __str__(self):
        return f"{self.source} writing log on {self.log_date}"
