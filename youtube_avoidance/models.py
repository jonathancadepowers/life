from django.db import models


class YouTubeAvoidanceLog(models.Model):
    """
    Represents a YouTube avoidance log entry.
    Tracks days when YouTube was successfully avoided.
    """
    source = models.CharField(
        max_length=50,
        help_text="Source of the log data (e.g., 'Manual', 'API')"
    )
    source_id = models.CharField(
        max_length=255,
        help_text="ID from the external source system",
        db_index=True
    )
    log_date = models.DateField(
        help_text="Date of the YouTube avoidance log"
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
        verbose_name = 'YouTube Avoidance Log'
        verbose_name_plural = 'YouTube Avoidance Logs'
        db_table = 'youtube_avoidance_logs'

    def __str__(self):
        return f"{self.source} log on {self.log_date.strftime('%Y-%m-%d')}"
