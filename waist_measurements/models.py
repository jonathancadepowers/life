from django.db import models


class WaistCircumferenceMeasurement(models.Model):
    """
    Stores waist circumference measurements.
    """
    source = models.CharField(
        max_length=50,
        help_text="Source of the measurement (e.g., 'Manual', 'App Name')"
    )
    source_id = models.CharField(
        max_length=255,
        help_text="ID from external source",
        db_index=True
    )
    log_date = models.DateField(
        db_index=True,
        help_text="Date when the measurement was taken"
    )
    measurement = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Waist circumference in inches"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-log_date']
        verbose_name = 'Waist Circumference Measurement'
        verbose_name_plural = 'Waist Circumference Measurements'
        db_table = 'waist_circumference_measurements'
        unique_together = ['source', 'source_id']

    def __str__(self):
        return f"{self.measurement}\" on {self.log_date.strftime('%Y-%m-%d')}"
