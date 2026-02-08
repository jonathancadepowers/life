from django.db import models


class WeighIn(models.Model):
    """
    Represents a weight measurement from various sources.
    """
    source = models.CharField(
        max_length=50,
        help_text="Source of the weight data (e.g., 'Whoop', 'Manual', 'Withings')"
    )
    source_id = models.CharField(
        max_length=255,
        help_text="ID from the external source system",
        db_index=True
    )
    measurement_time = models.DateTimeField(
        help_text="When the weight measurement was taken"
    )
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Weight in pounds (lbs)"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-measurement_time']
        unique_together = ['source', 'source_id']
        indexes = [
            models.Index(fields=['-measurement_time']),
            models.Index(fields=['source', 'source_id']),
        ]
        verbose_name = 'Weigh-in'
        verbose_name_plural = 'Weigh-ins'

    def __str__(self):
        return f"{self.weight} lbs on {self.measurement_time.strftime('%Y-%m-%d %H:%M')}"
