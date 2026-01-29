from django.db import models


class CalendarEvent(models.Model):
    """Calendar event imported from Outlook."""

    # Unique ID from Outlook for idempotent imports
    outlook_id = models.CharField(max_length=255, unique=True, db_index=True)

    # Event details
    subject = models.CharField(max_length=500)
    start = models.DateTimeField(db_index=True)
    end = models.DateTimeField()
    is_all_day = models.BooleanField(default=False)
    location = models.CharField(max_length=500, blank=True, default='')
    organizer = models.EmailField(max_length=255, blank=True, default='')
    body_preview = models.TextField(blank=True, default='')

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start']
        indexes = [
            models.Index(fields=['start', 'end']),
        ]

    def __str__(self):
        return f"{self.subject} ({self.start.strftime('%Y-%m-%d %H:%M')})"
