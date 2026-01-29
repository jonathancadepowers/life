from django.db import models


class Task(models.Model):
    """A task item."""

    title = models.CharField(max_length=255)
    details = models.TextField(blank=True, default='')
    critical = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
