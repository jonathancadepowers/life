from django.test import TestCase
from datetime import date
from .models import MonthlyObjective, get_default_timezone
from settings.models import Setting


class MonthlyObjectiveTimezoneTests(TestCase):
    """
    Tests to ensure that new MonthlyObjective rows get their timezone
    from the Settings table, not from hardcoded values.
    """

    def setUp(self):
        """Set up test data before each test"""
        # Clean up any existing settings from previous tests
        Setting.objects.filter(key='default_timezone_for_monthly_objectives').delete()

    def tearDown(self):
        """Clean up after each test"""
        # Clean up test data
        MonthlyObjective.objects.all().delete()
        Setting.objects.filter(key='default_timezone_for_monthly_objectives').delete()

    def test_new_objective_uses_timezone_from_settings(self):
        """
        Test that a new MonthlyObjective gets its timezone from the Settings table.
        """
        # Create the setting with a specific timezone
        Setting.set(
            key='default_timezone_for_monthly_objectives',
            value='America/Chicago',
            description='Test timezone setting'
        )

        # Create a new objective
        objective = MonthlyObjective.objects.create(
            objective_id='test_chicago',
            start=date(2025, 11, 1),
            end=date(2025, 11, 30),
            label='Test Objective',
            objective_value=30,
            objective_definition='SELECT COUNT(*) FROM test'
        )

        # Verify it uses the timezone from settings
        self.assertEqual(objective.timezone, 'America/Chicago')

    def test_changing_setting_affects_new_objectives_only(self):
        """
        Test that changing the setting affects new objectives but not existing ones.
        """
        # Create setting with Chicago timezone
        Setting.set(
            key='default_timezone_for_monthly_objectives',
            value='America/Chicago',
            description='Test timezone setting'
        )

        # Create first objective
        objective1 = MonthlyObjective.objects.create(
            objective_id='test_chicago_obj',
            start=date(2025, 11, 1),
            end=date(2025, 11, 30),
            label='Chicago Objective',
            objective_value=30,
            objective_definition='SELECT COUNT(*) FROM test'
        )
        self.assertEqual(objective1.timezone, 'America/Chicago')

        # Change the setting to New York timezone
        Setting.set(
            key='default_timezone_for_monthly_objectives',
            value='America/New_York',
            description='Updated timezone setting'
        )

        # Create second objective
        objective2 = MonthlyObjective.objects.create(
            objective_id='test_newyork_obj',
            start=date(2025, 12, 1),
            end=date(2025, 12, 31),
            label='New York Objective',
            objective_value=25,
            objective_definition='SELECT COUNT(*) FROM test'
        )

        # Refresh first objective from database
        objective1.refresh_from_db()

        # Verify first objective still has Chicago timezone (unchanged)
        self.assertEqual(objective1.timezone, 'America/Chicago')

        # Verify second objective has New York timezone (from updated setting)
        self.assertEqual(objective2.timezone, 'America/New_York')

    def test_fallback_timezone_when_setting_does_not_exist(self):
        """
        Test that the fallback timezone is used when the setting doesn't exist.
        """
        # Ensure no setting exists
        Setting.objects.filter(key='default_timezone_for_monthly_objectives').delete()

        # Create objective without setting present
        objective = MonthlyObjective.objects.create(
            objective_id='test_fallback',
            start=date(2025, 11, 1),
            end=date(2025, 11, 30),
            label='Fallback Test',
            objective_value=30,
            objective_definition='SELECT COUNT(*) FROM test'
        )

        # Should fall back to America/Chicago
        self.assertEqual(objective.timezone, 'America/Chicago')

    def test_get_default_timezone_function(self):
        """
        Test the get_default_timezone() helper function directly.
        """
        # Test with setting present
        Setting.set(
            key='default_timezone_for_monthly_objectives',
            value='America/Los_Angeles',
            description='Test timezone'
        )
        self.assertEqual(get_default_timezone(), 'America/Los_Angeles')

        # Test with setting absent
        Setting.objects.filter(key='default_timezone_for_monthly_objectives').delete()
        self.assertEqual(get_default_timezone(), 'America/Chicago')

    def test_multiple_objectives_same_setting(self):
        """
        Test that multiple objectives created with the same setting all get the same timezone.
        """
        # Set timezone to Denver
        Setting.set(
            key='default_timezone_for_monthly_objectives',
            value='America/Denver',
            description='Test timezone'
        )

        # Create multiple objectives
        objectives = []
        for month in range(1, 4):  # Jan, Feb, Mar
            obj = MonthlyObjective.objects.create(
                objective_id=f'test_2025_{month:02d}',
                start=date(2025, month, 1),
                end=date(2025, month, 28),
                label=f'Month {month} Objective',
                objective_value=20,
                objective_definition='SELECT COUNT(*) FROM test'
            )
            objectives.append(obj)

        # Verify all have Denver timezone
        for obj in objectives:
            self.assertEqual(obj.timezone, 'America/Denver')
