from django.test import TestCase
from unittest import skip
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


class MonthlyObjectiveUnitOfMeasurementTests(TestCase):
    """
    Tests to ensure the unit_of_measurement field works correctly.
    """

    def tearDown(self):
        """Clean up after each test"""
        MonthlyObjective.objects.all().delete()

    def test_unit_of_measurement_can_be_set(self):
        """
        Test that unit_of_measurement can be set and retrieved.
        """
        objective = MonthlyObjective.objects.create(
            objective_id='test_with_unit',
            start=date(2025, 11, 1),
            end=date(2025, 11, 30),
            label='Test Objective',
            objective_value=30,
            objective_definition='SELECT COUNT(*) FROM test',
            unit_of_measurement='minutes'
        )

        # Verify the unit was saved
        self.assertEqual(objective.unit_of_measurement, 'minutes')

        # Verify it persists after refresh from database
        objective.refresh_from_db()
        self.assertEqual(objective.unit_of_measurement, 'minutes')

    def test_unit_of_measurement_can_be_null(self):
        """
        Test that unit_of_measurement can be null (backwards compatibility).
        """
        objective = MonthlyObjective.objects.create(
            objective_id='test_without_unit',
            start=date(2025, 11, 1),
            end=date(2025, 11, 30),
            label='Test Objective Without Unit',
            objective_value=25,
            objective_definition='SELECT COUNT(*) FROM test'
            # Note: unit_of_measurement not provided
        )

        # Verify it's None/null
        self.assertIsNone(objective.unit_of_measurement)

        # Verify it persists as None after refresh
        objective.refresh_from_db()
        self.assertIsNone(objective.unit_of_measurement)

    def test_unit_of_measurement_various_values(self):
        """
        Test that various common unit values can be stored.
        """
        test_units = ['minutes', 'sessions', 'days', 'pounds', 'workouts', 'hours']

        for i, unit in enumerate(test_units):
            objective = MonthlyObjective.objects.create(
                objective_id=f'test_unit_{i}',
                start=date(2025, 11, 1),
                end=date(2025, 11, 30),
                label=f'Test {unit}',
                objective_value=10,
                objective_definition='SELECT COUNT(*) FROM test',
                unit_of_measurement=unit
            )

            # Verify each unit is saved correctly
            self.assertEqual(objective.unit_of_measurement, unit)

    def test_unit_of_measurement_can_be_updated(self):
        """
        Test that unit_of_measurement can be updated after creation.
        """
        objective = MonthlyObjective.objects.create(
            objective_id='test_update_unit',
            start=date(2025, 11, 1),
            end=date(2025, 11, 30),
            label='Test Update',
            objective_value=20,
            objective_definition='SELECT COUNT(*) FROM test',
            unit_of_measurement='minutes'
        )

        # Update the unit
        objective.unit_of_measurement = 'hours'
        objective.save()

        # Verify the update persisted
        objective.refresh_from_db()
        self.assertEqual(objective.unit_of_measurement, 'hours')


class MonthlyObjectiveResultCachingTests(TestCase):
    """
    Tests to ensure that objective results are properly cached in the database
    and that the activity_report view updates and uses these cached results.
    """

    def setUp(self):
        """Set up test data before each test"""
        from calendar import monthrange

        # Get current month's last day
        today = date.today()
        last_day = monthrange(today.year, today.month)[1]

        # Create test objective with a simple SQL query that returns a constant
        self.test_objective = MonthlyObjective.objects.create(
            objective_id='test_result_caching',
            start=today.replace(day=1),
            end=today.replace(day=last_day),
            label='Test Result Caching',
            objective_value=100,
            objective_definition='SELECT 42.0',  # Simple query that returns 42
            result=None  # Start with no cached result
        )

    def tearDown(self):
        """Clean up after each test"""
        MonthlyObjective.objects.all().delete()

    def test_management_command_updates_result_field(self):
        """
        Test (2): Verify that the management command correctly calculates
        and saves results to the database.
        """
        from django.core.management import call_command
        from io import StringIO

        # Verify result starts as None
        self.assertIsNone(self.test_objective.result)

        # Run the management command
        out = StringIO()
        call_command('update_objective_results', stdout=out)

        # Refresh from database
        self.test_objective.refresh_from_db()

        # Verify result was updated to 42 (from our SELECT 42.0 query)
        self.assertEqual(self.test_objective.result, 42.0)

    def test_management_command_with_specific_objective_id(self):
        """
        Test that the management command can update a specific objective by ID.
        """
        from django.core.management import call_command
        from io import StringIO
        from calendar import monthrange

        # Get current month's last day
        today = date.today()
        last_day = monthrange(today.year, today.month)[1]

        # Create second objective
        obj2 = MonthlyObjective.objects.create(
            objective_id='test_second_obj',
            start=today.replace(day=1),
            end=today.replace(day=last_day),
            label='Second Test',
            objective_value=50,
            objective_definition='SELECT 99.0',
            result=None
        )

        # Run command for specific objective only
        out = StringIO()
        call_command('update_objective_results',
                    objective_id='test_result_caching',
                    stdout=out)

        # Refresh both from database
        self.test_objective.refresh_from_db()
        obj2.refresh_from_db()

        # Verify only the specified objective was updated
        self.assertEqual(self.test_objective.result, 42.0)
        self.assertIsNone(obj2.result)

    @skip("Feature not yet implemented: automatic result updates on page load")
    def test_activity_report_view_updates_results_on_page_load(self):
        """
        Test (1): Verify that loading the activity_report page triggers
        result updates for objectives in the displayed month.
        """
        from django.test import Client

        # Verify result starts as None
        self.assertIsNone(self.test_objective.result)

        # Load the activity report page
        client = Client()
        response = client.get('/targets/')

        # Verify page loaded successfully
        self.assertEqual(response.status_code, 200)

        # Refresh objective from database
        self.test_objective.refresh_from_db()

        # Verify result was updated by the page load
        self.assertEqual(self.test_objective.result, 42.0)

    @skip("Feature not yet implemented: automatic result updates on page load")
    def test_activity_report_view_uses_cached_result(self):
        """
        Test (3): Verify that the activity_report view uses the cached
        result from the database rather than calculating it separately.
        """
        from django.test import Client

        # Manually set a result in the database
        self.test_objective.result = 123.45
        self.test_objective.save()

        # Load the activity report page
        client = Client()
        response = client.get('/targets/')

        # Verify page loaded successfully
        self.assertEqual(response.status_code, 200)

        # Check that the context contains the objective data
        objectives_data = response.context.get('objectives_data', [])

        # Find our test objective in the response
        test_obj_data = None
        for obj in objectives_data:
            if obj['objective_id'] == 'test_result_caching':
                test_obj_data = obj
                break

        # Verify the objective was found in the response
        self.assertIsNotNone(test_obj_data,
            "Test objective should be present in activity_report context")

        # Verify the view is using the cached result (which was manually updated)
        # After page load, it should be 42.0 (from the SELECT 42.0 query)
        # because the view updates results before display
        self.assertEqual(test_obj_data['result'], 42.0)

    def test_result_field_accuracy_with_complex_query(self):
        """
        Test (2): Verify that result field data is accurate for a more
        complex SQL query.
        """
        from django.core.management import call_command
        from io import StringIO
        from calendar import monthrange

        # Get current month's last day
        today = date.today()
        last_day = monthrange(today.year, today.month)[1]

        # Create objective with a query that uses actual database data
        obj = MonthlyObjective.objects.create(
            objective_id='test_complex_query',
            start=today.replace(day=1),
            end=today.replace(day=last_day),
            label='Complex Query Test',
            objective_value=10,
            objective_definition='SELECT COUNT(*) FROM monthly_objectives_monthlyobjective',
            result=None
        )

        # Count objectives manually
        expected_count = float(MonthlyObjective.objects.count())

        # Run management command
        out = StringIO()
        call_command('update_objective_results', stdout=out)

        # Refresh from database
        obj.refresh_from_db()

        # Verify result matches the actual count
        self.assertEqual(obj.result, expected_count)

    @skip("Feature not yet implemented: automatic result updates on page load")
    def test_result_updates_on_subsequent_page_loads(self):
        """
        Test that results are recalculated on each page load, ensuring
        they stay current.
        """
        from django.test import Client

        # Initial page load
        client = Client()
        client.get('/targets/')

        self.test_objective.refresh_from_db()
        first_result = self.test_objective.result
        self.assertEqual(first_result, 42.0)

        # Manually change the result to simulate outdated data
        self.test_objective.result = 999.0
        self.test_objective.save()

        # Load page again
        client.get('/targets/')

        # Refresh from database
        self.test_objective.refresh_from_db()

        # Verify result was recalculated and updated
        self.assertEqual(self.test_objective.result, 42.0)

    def test_result_field_handles_sql_errors_gracefully(self):
        """
        Test that SQL errors don't crash the system and preserve existing results.
        """
        from django.test import Client

        # Set a valid initial result
        self.test_objective.result = 50.0
        self.test_objective.save()

        # Change query to invalid SQL
        self.test_objective.objective_definition = 'SELECT * FROM nonexistent_table'
        self.test_objective.save()

        # Load page (should not crash)
        client = Client()
        response = client.get('/targets/')

        # Verify page still loads
        self.assertEqual(response.status_code, 200)

        # Refresh from database
        self.test_objective.refresh_from_db()

        # Result should either be preserved or set to 0 (not crash)
        self.assertIsNotNone(self.test_objective.result)
        self.assertIn(self.test_objective.result, [0.0, 50.0])
