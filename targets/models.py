from django.db import models


class Target(models.Model):
    """
    Represents a target associated with a goal.
    """
    target_id = models.CharField(
        max_length=255,
        primary_key=True,
        help_text="Unique identifier for the target"
    )
    target_name = models.CharField(
        max_length=255,
        help_text="Name of the target"
    )
    goal_id = models.ForeignKey(
        'goals.Goal',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Associated goal (optional)"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['target_name']
        verbose_name = 'Target'
        verbose_name_plural = 'Targets'

    def __str__(self):
        return self.target_name


class DailyAgenda(models.Model):
    """
    Represents a user's daily agenda with up to 3 targets.
    """
    date = models.DateField(
        help_text="Date for this agenda",
        db_index=True
    )

    # Target 1
    project_1 = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_1',
        help_text="Project for target 1"
    )
    goal_1 = models.ForeignKey(
        'goals.Goal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_1',
        help_text="Goal for target 1"
    )
    target_1 = models.ForeignKey(
        'Target',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_1',
        help_text="Target 1"
    )

    # Target 2
    project_2 = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_2',
        help_text="Project for target 2"
    )
    goal_2 = models.ForeignKey(
        'goals.Goal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_2',
        help_text="Goal for target 2"
    )
    target_2 = models.ForeignKey(
        'Target',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_2',
        help_text="Target 2"
    )

    # Target 3
    project_3 = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_3',
        help_text="Project for target 3"
    )
    goal_3 = models.ForeignKey(
        'goals.Goal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_3',
        help_text="Goal for target 3"
    )
    target_3 = models.ForeignKey(
        'Target',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_3',
        help_text="Target 3"
    )

    # Score fields (0 = sad, 0.5 = neutral, 1 = happy)
    target_1_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Score for target 1 (0, 0.5, or 1)"
    )
    target_2_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Score for target 2 (0, 0.5, or 1)"
    )
    target_3_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Score for target 3 (0, 0.5, or 1)"
    )

    # Overall day score (calculated from target scores)
    day_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Overall score for the day (0.0 to 1.0, calculated from target scores)"
    )

    # Notes field (supports markdown)
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Free-form notes for the day (supports Markdown)"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Daily Agenda'
        verbose_name_plural = 'Daily Agendas'
        unique_together = ['date']

    def __str__(self):
        return f"Agenda for {self.date}"
