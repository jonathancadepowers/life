from django.db import models


class ToDo(models.Model):
    """A to-do item."""

    title = models.CharField(max_length=255)
    details = models.TextField(blank=True, default='')
    critical = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'To-Do'
        verbose_name_plural = 'To-Dos'

    def __str__(self):
        return self.title
