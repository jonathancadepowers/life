from django.db import models


class TaskState(models.Model):
    """A state/status for tasks."""

    name = models.CharField(max_length=100, unique=True)
    order = models.IntegerField(default=0)
    bootstrap_icon = models.CharField(max_length=50, blank=True, default="")  # e.g., 'bi-inbox'
    is_system = models.BooleanField(default=False)  # System states like 'Abandoned' can't be deleted/reordered
    is_terminal = models.BooleanField(default=False)  # Terminal state marks tasks as "completed"
    show_signal_noise = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # If this state is being set as terminal, unset any other terminal states
        if self.is_terminal:
            TaskState.objects.filter(is_terminal=True).exclude(pk=self.pk).update(is_terminal=False)
        super().save(*args, **kwargs)


class TaskTag(models.Model):
    """A tag that can be applied to tasks."""

    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Task(models.Model):
    """A task item."""

    title = models.CharField(max_length=255)
    details = models.TextField(blank=True, default="")
    critical = models.BooleanField(default=False)
    state = models.ForeignKey(TaskState, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    tags = models.ManyToManyField(TaskTag, blank=True, related_name="tasks")
    order = models.IntegerField(default=0)
    deadline = models.DateField(null=True, blank=True)
    deadline_dismissed = models.BooleanField(default=False)
    state_changed_at = models.DateTimeField(null=True, blank=True)  # When task entered current state
    done_for_day = models.DateField(null=True, blank=True)  # Date when task was marked "Done for Today"
    is_signal = models.BooleanField(default=False)  # Signal zone in Signal/Noise priority system
    signal_slot = models.IntegerField(null=True, blank=True)  # 0, 1, or 2 for position within signal zone
    noise_slot = models.IntegerField(null=True, blank=True)  # 0-N for position within noise zone (groups of 3)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return self.title


class TaskSchedule(models.Model):
    """A scheduled time slot for a task on the calendar."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="schedules")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]
        indexes = [
            models.Index(fields=["start_time"]),
            models.Index(fields=["task", "start_time"]),
        ]

    def __str__(self):
        return f"{self.task.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"


class TimeBlock(models.Model):
    """A time block event on the calendar."""

    name = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    tasks = models.ManyToManyField(Task, blank=True, related_name="time_blocks")
    task_order = models.JSONField(default=list, blank=True)  # Store task IDs in display order
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return self.name

    def get_ordered_tasks(self):
        """Return tasks in the order specified by task_order."""
        if not self.task_order:
            return list(self.tasks.all())

        # Create a dict for quick lookup
        tasks_dict = {t.id: t for t in self.tasks.all()}

        # Return tasks in order, followed by any not in task_order
        ordered = [tasks_dict[tid] for tid in self.task_order if tid in tasks_dict]
        remaining = [t for t in tasks_dict.values() if t.id not in self.task_order]
        return ordered + remaining


class TaskDetailTemplate(models.Model):
    """A reusable template for task details markdown content."""

    name = models.CharField(max_length=100)
    content = models.TextField()
    is_default = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # If this template is being set as default, unset any other defaults
        if self.is_default:
            TaskDetailTemplate.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class TaskView(models.Model):
    """A saved view configuration for task filtering and grouping."""

    name = models.CharField(max_length=100)
    settings = models.JSONField(default=dict)  # Stores all filter/group settings
    is_default = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # If this view is being set as default, unset any other defaults
        if self.is_default:
            TaskView.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
