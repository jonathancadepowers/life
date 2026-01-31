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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title


class TaskSchedule(models.Model):
    """A scheduled time slot for a task on the calendar."""

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['start_time']),
            models.Index(fields=['task', 'start_time']),
        ]

    def __str__(self):
        return f"{self.task.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"


class TimeBlock(models.Model):
    """A time block event on the calendar."""

    name = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return self.name
