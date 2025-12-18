from django.db import models


class WaistMeasurement(models.Model):
    """
    Stores waist circumference measurements.
    """
    source = models.CharField(
        max_length=50,
        help_text="Source of the measurement (e.g., 'Manual', 'App Name')"
    )
    measurement_time = models.DateTimeField(
        db_index=True,
        help_text="Date and time when the measurement was taken"
    )
    waist_circumference = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Waist circumference in inches"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-measurement_time']
        verbose_name = 'Waist Measurement'
        verbose_name_plural = 'Waist Measurements'
        db_table = 'waist_measurements_waistmeasurement'

    def __str__(self):
        return f"{self.waist_circumference}\" on {self.measurement_time.strftime('%Y-%m-%d')}"
