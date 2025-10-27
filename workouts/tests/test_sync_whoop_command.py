"""
Phase 2 Tests: Sync Command

These tests validate the sync_whoop management command that fetches
workouts from Whoop API and saves them to the database.
"""
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from datetime import datetime
from unittest import mock
from io import StringIO

from oauth_integration.models import OAuthCredential
from workouts.models import Workout


class TestSyncWhoopCommand(TestCase):
    """Test sync_whoop management command"""

    def setUp(self):
        """Set up test database with OAuth credentials"""
        self.credential = OAuthCredential.objects.create(
            provider='whoop',
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='http://localhost:8000/whoop/callback',
            access_token='valid_access_token',
            refresh_token='valid_refresh_token',
            token_expires_at=timezone.now() + timezone.timedelta(hours=1)
        )

        # Sample workout data from Whoop API
        self.sample_workout_data = [
            {
                'id': 'workout_123',
                'start': '2025-10-27T12:00:00.000Z',
                'end': '2025-10-27T13:00:00.000Z',
                'sport_id': 63,  # Running
                'score': {
                    'average_heart_rate': 150,
                    'max_heart_rate': 180,
                    'kilojoule': 2000  # ~478 calories
                }
            },
            {
                'id': 'workout_456',
                'start': '2025-10-26T10:00:00.000Z',
                'end': '2025-10-26T11:30:00.000Z',
                'sport_id': 48,  # Cycling
                'score': {
                    'average_heart_rate': 140,
                    'max_heart_rate': 170,
                    'kilojoule': 3000  # ~717 calories
                }
            }
        ]

    @mock.patch('workouts.services.whoop_client.WhoopAPIClient.get_all_workouts')
    def test_sync_creates_new_workouts(self, mock_get_workouts):
        """Should create workout records from API data"""
        # Mock: API returns 2 workouts
        mock_get_workouts.return_value = self.sample_workout_data

        # Run the sync command
        out = StringIO()
        call_command('sync_whoop', days=7, stdout=out)

        # Assert: 2 workouts created in database
        self.assertEqual(Workout.objects.count(), 2)

        # Assert: First workout saved correctly
        workout1 = Workout.objects.get(source_id='workout_123')
        self.assertEqual(workout1.source, 'Whoop')
        self.assertEqual(workout1.sport_id, 63)
        self.assertEqual(workout1.average_heart_rate, 150)
        self.assertEqual(workout1.max_heart_rate, 180)
        self.assertAlmostEqual(workout1.calories_burned, 478, delta=1)

        # Assert: Second workout saved correctly
        workout2 = Workout.objects.get(source_id='workout_456')
        self.assertEqual(workout2.sport_id, 48)

        # Assert: Command output shows success
        output = out.getvalue()
        self.assertIn('Created: 2', output)
        self.assertIn('Sync completed successfully', output)

    @mock.patch('workouts.services.whoop_client.WhoopAPIClient.get_all_workouts')
    def test_sync_updates_existing_workouts(self, mock_get_workouts):
        """Should update existing workouts using source_id, not create duplicates"""
        # Setup: Create existing workout in database
        existing_workout = Workout.objects.create(
            source='Whoop',
            source_id='workout_123',
            start=timezone.make_aware(datetime(2025, 10, 27, 12, 0, 0)),
            end=timezone.make_aware(datetime(2025, 10, 27, 13, 0, 0)),
            sport_id=63,
            average_heart_rate=145,  # Old value
            max_heart_rate=175,  # Old value
            calories_burned=450  # Old value
        )

        # Mock: API returns updated data for same workout
        updated_workout_data = [{
            'id': 'workout_123',
            'start': '2025-10-27T12:00:00.000Z',
            'end': '2025-10-27T13:00:00.000Z',
            'sport_id': 63,
            'score': {
                'average_heart_rate': 150,  # Updated
                'max_heart_rate': 180,  # Updated
                'kilojoule': 2000  # Updated
            }
        }]
        mock_get_workouts.return_value = updated_workout_data

        # Run the sync command
        out = StringIO()
        call_command('sync_whoop', days=7, stdout=out)

        # Assert: Still only 1 workout (not duplicated)
        self.assertEqual(Workout.objects.count(), 1)

        # Assert: Workout was updated with new values
        existing_workout.refresh_from_db()
        self.assertEqual(existing_workout.average_heart_rate, 150)
        self.assertEqual(existing_workout.max_heart_rate, 180)
        self.assertAlmostEqual(existing_workout.calories_burned, 478, delta=1)

        # Assert: Command output shows update
        output = out.getvalue()
        self.assertIn('Created: 0', output)
        self.assertIn('Updated: 1', output)

    @mock.patch('workouts.services.whoop_client.WhoopAPIClient.get_all_workouts')
    def test_sync_skips_unscored_workouts(self, mock_get_workouts):
        """Should skip workouts without scores (not yet scored by Whoop)"""
        # Mock: API returns workout with score=None
        unscored_workout_data = [
            {
                'id': 'workout_unscored',
                'start': '2025-10-27T12:00:00.000Z',
                'end': '2025-10-27T13:00:00.000Z',
                'sport_id': 63,
                'score': None  # Not yet scored
            },
            self.sample_workout_data[0]  # One valid workout
        ]
        mock_get_workouts.return_value = unscored_workout_data

        # Run the sync command
        out = StringIO()
        call_command('sync_whoop', days=7, stdout=out)

        # Assert: Only scored workout was saved
        self.assertEqual(Workout.objects.count(), 1)
        self.assertEqual(Workout.objects.first().source_id, 'workout_123')

        # Assert: Command output shows 1 skipped
        output = out.getvalue()
        self.assertIn('Skipped: 1', output)
        self.assertIn('not yet scored', output)

    @mock.patch('workouts.management.commands.sync_whoop.WhoopAPIClient')
    def test_sync_raises_on_auth_error(self, mock_client_class):
        """Should raise exception when authentication fails (for sync_all to catch)"""
        # Mock: Client initialization and method call
        mock_client_instance = mock.Mock()
        mock_client_class.return_value = mock_client_instance

        # Mock: get_all_workouts raises ValueError (expired refresh token)
        mock_client_instance.get_all_workouts.side_effect = ValueError(
            "Whoop refresh token expired or invalid. Please re-authenticate by running: "
            "python manage.py whoop_auth"
        )

        # Assert: Command raises exception (not caught internally)
        out = StringIO()
        err = StringIO()
        with self.assertRaises(ValueError) as context:
            call_command('sync_whoop', days=7, stdout=out, stderr=err)

        # Assert: Error message is preserved for sync_all to display
        error_message = str(context.exception)
        self.assertIn('Whoop refresh token expired or invalid', error_message)
        self.assertIn('python manage.py whoop_auth', error_message)

    @mock.patch('workouts.services.whoop_client.WhoopAPIClient.get_all_workouts')
    def test_sync_handles_malformed_workout_data(self, mock_get_workouts):
        """Should skip workouts with missing required fields"""
        # Mock: API returns malformed workout data
        malformed_data = [
            {
                'id': 'workout_good',
                'start': '2025-10-27T12:00:00.000Z',
                'end': '2025-10-27T13:00:00.000Z',
                'sport_id': 63,
                'score': {'average_heart_rate': 150, 'max_heart_rate': 180, 'kilojoule': 2000}
            },
            {
                'id': 'workout_missing_start',
                # 'start': missing
                'end': '2025-10-27T13:00:00.000Z',
                'sport_id': 63,
                'score': {'average_heart_rate': 150, 'max_heart_rate': 180, 'kilojoule': 2000}
            },
            {
                # 'id': missing
                'start': '2025-10-27T12:00:00.000Z',
                'end': '2025-10-27T13:00:00.000Z',
                'sport_id': 63,
                'score': {'average_heart_rate': 150, 'max_heart_rate': 180, 'kilojoule': 2000}
            }
        ]
        mock_get_workouts.return_value = malformed_data

        # Run the sync command
        out = StringIO()
        call_command('sync_whoop', days=7, stdout=out)

        # Assert: Only valid workout was saved
        self.assertEqual(Workout.objects.count(), 1)
        self.assertEqual(Workout.objects.first().source_id, 'workout_good')

        # Assert: Command output shows 2 skipped
        output = out.getvalue()
        self.assertIn('Skipped: 2', output)

    @mock.patch('workouts.services.whoop_client.WhoopAPIClient.get_all_workouts')
    def test_sync_converts_kilojoules_to_calories(self, mock_get_workouts):
        """Should convert kilojoules to calories correctly (1 kJ = 0.239006 kcal)"""
        # Mock: Workout with 4184 kilojoules (should be ~1000 calories)
        workout_data = [{
            'id': 'workout_cal_test',
            'start': '2025-10-27T12:00:00.000Z',
            'end': '2025-10-27T13:00:00.000Z',
            'sport_id': 63,
            'score': {
                'average_heart_rate': 150,
                'max_heart_rate': 180,
                'kilojoule': 4184  # Exactly 1000 calories
            }
        }]
        mock_get_workouts.return_value = workout_data

        # Run the sync command
        call_command('sync_whoop', days=7, stdout=StringIO())

        # Assert: Calories calculated correctly
        workout = Workout.objects.get(source_id='workout_cal_test')
        self.assertAlmostEqual(workout.calories_burned, 1000, delta=1)
