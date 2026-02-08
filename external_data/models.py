from django.db import models


class WhoopSportId(models.Model):
    """
    Reference table for Whoop sport IDs and their corresponding sport names.
    Source: https://developer.whoop.com/docs/developing/user-data/workout/
    """

    sport_id = models.IntegerField(primary_key=True, help_text="Whoop sport ID")
    sport_name = models.CharField(max_length=100, help_text="Name of the sport/activity")

    class Meta:
        db_table = "whoop_sport_ids"
        verbose_name = "Whoop Sport ID"
        verbose_name_plural = "Whoop Sport IDs"
        ordering = ["sport_id"]

    def __str__(self):
        return f"{self.sport_id}: {self.sport_name}"
