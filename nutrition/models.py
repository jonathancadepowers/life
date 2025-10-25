from django.db import models


class NutritionEntry(models.Model):
    """
    Represents a nutrition entry from various sources (Manual, MyFitnessPal, etc.)
    """
    source = models.CharField(
        max_length=50,
        help_text="Source of the nutrition data (e.g., 'Manual', 'MyFitnessPal')"
    )
    source_id = models.CharField(
        max_length=255,
        help_text="ID from the external source system",
        db_index=True
    )
    consumption_date = models.DateTimeField(
        help_text="When the food was consumed (local datetime)"
    )
    calories = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text="Total calories consumed"
    )
    fat = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Fat in grams"
    )
    carbs = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Carbohydrates in grams"
    )
    protein = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Protein in grams"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-consumption_date']
        unique_together = ['source', 'source_id']
        indexes = [
            models.Index(fields=['-consumption_date']),
            models.Index(fields=['source', 'source_id']),
        ]
        verbose_name = 'Nutrition Entry'
        verbose_name_plural = 'Nutrition Entries'

    def __str__(self):
        return f"{self.source} entry: {self.calories} cal on {self.consumption_date.strftime('%Y-%m-%d')}"
