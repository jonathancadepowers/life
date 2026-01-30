from django.db import models


class TaskState(models.Model):
    """A state/status for tasks."""

    name = models.CharField(max_length=100, unique=True)
    order = models.IntegerField(default=0)
    bootstrap_icon = models.CharField(max_length=50, blank=True, default='')  # e.g., 'bi-inbox'
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class TaskTag(models.Model):
    """A tag that can be applied to tasks."""

    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Task(models.Model):
    """A task item."""

    title = models.CharField(max_length=255)
    details = models.TextField(blank=True, default='')
    critical = models.BooleanField(default=False)
    state = models.ForeignKey(
        TaskState,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    tags = models.ManyToManyField(
        TaskTag,
        blank=True,
        related_name='tasks'
    )
    order = models.IntegerField(default=0)
    calendar_time = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title
