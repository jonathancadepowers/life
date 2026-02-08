from django.db import models

PROJECT_MODEL = 'projects.Project'
GOAL_MODEL = 'goals.Goal'


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
        PROJECT_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_1',
        help_text="Project for target 1"
    )
    goal_1 = models.ForeignKey(
        GOAL_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_1',
        help_text="Goal for target 1"
    )
    target_1 = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Target 1 text"
    )

    # Target 2
    project_2 = models.ForeignKey(
        PROJECT_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_2',
        help_text="Project for target 2"
    )
    goal_2 = models.ForeignKey(
        GOAL_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_2',
        help_text="Goal for target 2"
    )
    target_2 = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Target 2 text"
    )

    # Target 3
    project_3 = models.ForeignKey(
        PROJECT_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_3',
        help_text="Project for target 3"
    )
    goal_3 = models.ForeignKey(
        GOAL_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_agendas_3',
        help_text="Goal for target 3"
    )
    target_3 = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Target 3 text"
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

    # Other plans field (supports markdown)
    other_plans = models.TextField(
        blank=True,
        default='',
        help_text="Other plans or notes for the day (supports Markdown)"
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
