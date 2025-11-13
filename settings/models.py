from django.db import models


class LifeTrackerColumn(models.Model):
    """
    Configuration for each column in the Life Tracker page.
    """
    column_name = models.CharField(
        max_length=50,
        unique=True,
        primary_key=True,
        help_text="Internal name of the column (e.g., 'run', 'fast', 'strength')"
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Display name shown in the column header"
    )
    tooltip_text = models.TextField(
        help_text="Help text that appears when hovering over the column header"
    )
    sql_query = models.TextField(
        help_text="SQL query to determine if checkbox should appear. Available parameters: :day_start, :day_end. Query should return a count."
    )
    order = models.IntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this column is currently enabled"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'column_name']
        verbose_name = 'Life Tracker Column'
        verbose_name_plural = 'Life Tracker Columns'

    def __str__(self):
        return f"{self.display_name} ({self.column_name})"


class Setting(models.Model):
    """
    Stores application-wide settings as key-value pairs.
    Provides a flexible way to store configuration that can be modified without code changes.
    """
    key = models.CharField(
        max_length=255,
        unique=True,
        primary_key=True,
        help_text="Unique identifier for this setting"
    )
    value = models.TextField(
        help_text="Value for this setting"
    )
    description = models.TextField(
        blank=True,
        help_text="Human-readable description of what this setting controls"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Setting'
        verbose_name_plural = 'Settings'

    def __str__(self):
        return f"{self.key}: {self.value[:50]}"

    @classmethod
    def get(cls, key, default=None):
        """
        Get a setting value by key. Returns default if not found.

        Usage:
            timezone = Setting.get('default_timezone_for_monthly_objectives', 'America/Chicago')
        """
        try:
            return cls.objects.get(pk=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value, description=''):
        """
        Set a setting value. Creates if doesn't exist, updates if it does.

        Usage:
            Setting.set('default_timezone_for_monthly_objectives', 'America/Chicago',
                       'Default timezone for new monthly objectives')
        """
        obj, created = cls.objects.update_or_create(
            key=key,
            defaults={'value': value, 'description': description}
        )
        return obj
