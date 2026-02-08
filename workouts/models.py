from django.db import models


class Workout(models.Model):
    """
    Represents a workout/exercise session from various sources (Whoop, etc.)
    """

    source = models.CharField(max_length=50, help_text="Source of the workout data (e.g., 'Whoop', 'Manual')")
    source_id = models.CharField(max_length=255, help_text="ID from the external source system", db_index=True)
    start = models.DateTimeField(help_text="Workout start time")
    end = models.DateTimeField(help_text="Workout end time")
    sport_id = models.IntegerField(help_text="Sport/activity type ID")
    average_heart_rate = models.IntegerField(null=True, blank=True, help_text="Average heart rate during workout (bpm)")
    max_heart_rate = models.IntegerField(null=True, blank=True, help_text="Maximum heart rate during workout (bpm)")
    calories_burned = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, help_text="Total calories burned during workout"
    )
    distance_in_miles = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Distance covered in miles (for applicable sports)",
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start"]
        unique_together = ["source", "source_id"]
        indexes = [
            models.Index(fields=["-start"]),
            models.Index(fields=["source", "source_id"]),
        ]

    def __str__(self):
        return f"{self.source} workout on {self.start.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration(self):
        """Calculate workout duration"""
        return self.end - self.start

    @property
    def duration_minutes(self):
        """Calculate workout duration in minutes"""
        return (self.end - self.start).total_seconds() / 60
