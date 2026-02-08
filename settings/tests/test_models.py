from datetime import date

from django.db import IntegrityError
from django.test import TestCase

from settings.models import LifeTrackerColumn, Setting


class LifeTrackerColumnTests(TestCase):
    """Tests for the LifeTrackerColumn model."""

    def _create_column(self, **kwargs):
        """Helper to create a LifeTrackerColumn with sensible defaults.

        Uses 'test_habit' as the default column_name to avoid clashing
        with columns seeded by the data migration.
        """
        defaults = {
            'column_name': 'test_habit',
            'display_name': 'Test Habit',
            'tooltip_text': 'Did you do the test habit today?',
            'sql_query': 'SELECT COUNT(*) FROM workouts_workout WHERE 1=1',
        }
        defaults.update(kwargs)
        return LifeTrackerColumn.objects.create(**defaults)

    def test_create_column_with_required_fields(self):
        """Creating a column with all required fields should succeed."""
        column = self._create_column()
        self.assertEqual(column.column_name, 'test_habit')
        self.assertEqual(column.display_name, 'Test Habit')
        self.assertEqual(column.tooltip_text, 'Did you do the test habit today?')
        self.assertIn('SELECT', column.sql_query)
        self.assertIsNotNone(column.pk)

    def test_str_returns_display_name_and_column_name(self):
        """__str__ should return 'display_name (column_name)'."""
        column = self._create_column(column_name='test_fasting', display_name='Fasting')
        self.assertEqual(str(column), 'Fasting (test_fasting)')

    # ------------------------------------------------------------------
    # is_active_on tests
    # ------------------------------------------------------------------

    def test_is_active_on_no_start_date_returns_false(self):
        """A column with no start_date is never active."""
        column = self._create_column(start_date=None)
        self.assertFalse(column.is_active_on(date(2026, 1, 15)))

    def test_is_active_on_date_before_start_date_returns_false(self):
        """A date before start_date should return False."""
        column = self._create_column(start_date=date(2026, 2, 1))
        self.assertFalse(column.is_active_on(date(2026, 1, 15)))

    def test_is_active_on_ongoing_and_date_gte_start(self):
        """With end_date='ongoing', any date >= start_date should be active."""
        column = self._create_column(
            start_date=date(2026, 1, 1),
            end_date='ongoing',
        )
        self.assertTrue(column.is_active_on(date(2026, 1, 1)))
        self.assertTrue(column.is_active_on(date(2030, 6, 15)))

    def test_is_active_on_date_within_start_and_end(self):
        """A date between start_date and a concrete end_date should be active."""
        column = self._create_column(
            start_date=date(2026, 1, 1),
            end_date='2026-03-31',
        )
        self.assertTrue(column.is_active_on(date(2026, 2, 15)))
        # Boundary: exactly on end_date
        self.assertTrue(column.is_active_on(date(2026, 3, 31)))

    def test_is_active_on_date_after_end_date_returns_false(self):
        """A date after the end_date should return False."""
        column = self._create_column(
            start_date=date(2026, 1, 1),
            end_date='2026-03-31',
        )
        self.assertFalse(column.is_active_on(date(2026, 4, 1)))

    # ------------------------------------------------------------------
    # Unique constraint on column_name
    # ------------------------------------------------------------------

    def test_column_name_unique_constraint(self):
        """Two columns with the same column_name should raise IntegrityError."""
        self._create_column(column_name='test_unique')
        with self.assertRaises(IntegrityError):
            self._create_column(column_name='test_unique', display_name='Duplicate')

    # ------------------------------------------------------------------
    # Self-referential parent FK
    # ------------------------------------------------------------------

    def test_parent_fk_self_referential_set_null(self):
        """Deleting a parent column should set children's parent to NULL."""
        parent = self._create_column(column_name='test_exercise', display_name='Exercise')
        child = self._create_column(
            column_name='test_child',
            display_name='Child Habit',
            parent=parent,
        )
        self.assertEqual(child.parent, parent)

        parent.delete()
        child.refresh_from_db()
        self.assertIsNone(child.parent)


class SettingTests(TestCase):
    """Tests for the Setting model."""

    def test_create_setting_with_key_and_value(self):
        """Creating a setting with key (PK) and value should work."""
        setting = Setting.objects.create(key='timezone', value='America/Chicago')
        self.assertEqual(setting.pk, 'timezone')
        self.assertEqual(setting.value, 'America/Chicago')

    def test_str_shows_key_and_truncated_value(self):
        """__str__ should show 'key: value' with value truncated to 50 chars."""
        short = Setting.objects.create(key='short', value='hello')
        self.assertEqual(str(short), 'short: hello')

        long_value = 'x' * 100
        long_setting = Setting.objects.create(key='long', value=long_value)
        self.assertEqual(str(long_setting), f'long: {"x" * 50}')

    def test_get_returns_value_when_exists(self):
        """Setting.get should return the value for an existing key."""
        Setting.objects.create(key='color', value='blue')
        self.assertEqual(Setting.get('color'), 'blue')

    def test_get_returns_default_for_missing_key(self):
        """Setting.get should return the default for a missing key."""
        self.assertIsNone(Setting.get('missing'))
        self.assertEqual(Setting.get('missing', 'fallback'), 'fallback')

    def test_set_creates_new_setting(self):
        """Setting.set should create a new setting if it doesn't exist."""
        Setting.set('new_key', 'new_value')
        self.assertEqual(Setting.objects.get(pk='new_key').value, 'new_value')

    def test_set_updates_existing_setting(self):
        """Setting.set should update the value of an existing setting."""
        Setting.set('key', 'original')
        Setting.set('key', 'updated')
        self.assertEqual(Setting.objects.get(pk='key').value, 'updated')
        # Ensure only one row exists
        self.assertEqual(Setting.objects.filter(pk='key').count(), 1)
