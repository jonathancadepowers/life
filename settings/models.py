from django.db import models


class LifeTrackerColumn(models.Model):
    """
    Configuration for each column in the Life Tracker page.
    """
    column_name = models.CharField(
        max_length=50,
        unique=True,
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
    details_display = models.TextField(
        blank=True,
        default='',
        help_text="Text configuration for details shown when hovering over checkmarks"
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when this habit becomes active"
    )
    end_date = models.CharField(
        max_length=20,
        default='ongoing',
        help_text="Date when this habit ends (YYYY-MM-DD) or 'ongoing'"
    )
    icon = models.CharField(
        max_length=50,
        default='bi-circle',
        help_text="Bootstrap icon class (e.g., 'bi-activity', 'bi-clock-history')"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        help_text="Parent habit (optional)"
    )

    # UI Configuration - Add button and modal settings
    has_add_button = models.BooleanField(
        default=False,
        help_text="Show + button on hover for empty cells"
    )
    modal_type = models.CharField(
        max_length=50,
        blank=True,
        default='',
        choices=[
            ('', 'No modal'),
            ('simple_confirm', 'Simple Yes/No confirmation'),
            ('duration_select', 'Duration selection (like fasting)'),
        ],
        help_text="Type of modal to show when + button is clicked"
    )
    modal_title = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Title shown in the modal header"
    )
    modal_body_text = models.TextField(
        blank=True,
        default='',
        help_text="Main text/question shown in modal body"
    )
    create_endpoint = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Django URL name for creating records (e.g., 'fasting:log_fast')"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Life Tracker Column'
        verbose_name_plural = 'Life Tracker Columns'

    def __str__(self):
        return f"{self.display_name} ({self.column_name})"

    def is_active_on(self, date):
        """
        Check if this habit is active on a given date.
        Returns True if the date falls within the habit's active period.
        """
        from datetime import datetime

        # If no start_date, assume it's not active
        if not self.start_date:
            return False

        # Check if date is after start_date
        if date < self.start_date:
            return False

        # If end_date is 'ongoing', it's active
        if self.end_date == 'ongoing':
            return True

        # Otherwise, parse end_date and check if date is before it
        try:
            end_date_obj = datetime.strptime(self.end_date, '%Y-%m-%d').date()
            return date <= end_date_obj
        except (ValueError, AttributeError):
            # If end_date is invalid, treat as ongoing
            return True


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
