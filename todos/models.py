from django.db import models


class TaskContext(models.Model):
    """A context/category for tasks."""

    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default='#6B9080')  # HEX color
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class TaskState(models.Model):
    """A state/status for tasks."""

    name = models.CharField(max_length=100, unique=True)
    is_terminal = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    bootstrap_icon = models.CharField(max_length=50, blank=True, default='')  # e.g., 'bi-inbox'
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Task(models.Model):
    """A task item."""

    title = models.CharField(max_length=255)
    details = models.TextField(blank=True, default='')
    critical = models.BooleanField(default=False)
    today = models.BooleanField(default=False)
    context = models.ForeignKey(
        TaskContext,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    state = models.ForeignKey(
        TaskState,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title
