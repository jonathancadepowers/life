from django.db import models


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
