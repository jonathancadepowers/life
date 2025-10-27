"""
Phase 2 Tests: Sync Command

These tests validate the sync_withings management command that fetches
weight measurements from Withings API and saves them to the database.
"""
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from datetime import datetime
from unittest import mock
from io import StringIO

from oauth_integration.models import OAuthCredential
from weight.models import WeighIn


class TestSyncWithingsCommand(TestCase):
    """Test sync_withings management command"""

    def setUp(self):
        """Set up test database with OAuth credentials"""
        self.credential = OAuthCredential.objects.create(
            provider='withings',
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='http://localhost:8000/oauth/withings/callback/',
            access_token='valid_access_token',
            refresh_token='valid_refresh_token',
            token_expires_at=timezone.now() + timezone.timedelta(hours=1)
        )

        # Sample measurement data from Withings API
        self.sample_measurement_data = {
            'status': 0,
            'body': {
                'measuregrps': [
                    {
                        'grpid': 123456789,
                        'date': 1698235200,  # Unix timestamp
                        'measures': [
                            {'value': 75000, 'type': 1, 'unit': -3}  # 75.000 kg
                        ]
                    },
                    {
                        'grpid': 123456790,
                        'date': 1698148800,
                        'measures': [
                            {'value': 74500, 'type': 1, 'unit': -3}  # 74.500 kg
                        ]
                    }
                ]
            }
        }

    @mock.patch('weight.services.withings_client.WithingsAPIClient.get_weight_measurements')
    def test_sync_creates_new_measurements(self, mock_get_weight_measurements):
        """Should create weight measurement records from API data"""
        # Mock: API returns 2 measurements
        mock_get_weight_measurements.return_value = self.sample_measurement_data

        # Run the sync command
        out = StringIO()
        call_command('sync_withings', days=7, stdout=out)

        # Assert: 2 measurements created in database
        self.assertEqual(WeighIn.objects.count(), 2)

        # Assert: First measurement saved correctly
        weighin1 = WeighIn.objects.get(source_id='123456789')
        self.assertEqual(weighin1.source, 'Withings')
        self.assertEqual(weighin1.weight_kg, 75.0)

        # Assert: Second measurement saved correctly
        weighin2 = WeighIn.objects.get(source_id='123456790')
        self.assertEqual(weighin2.weight_kg, 74.5)

        # Assert: Command output shows success
        output = out.getvalue()
        self.assertIn('Created: 2', output)
        self.assertIn('Sync completed successfully', output)

    @mock.patch('weight.services.withings_client.WithingsAPIClient.get_weight_measurements')
    def test_sync_updates_existing_measurements(self, mock_get_weight_measurements):
        """Should update existing measurements using source_id, not create duplicates"""
        # Setup: Create existing measurement in database
        existing_weighin = WeighIn.objects.create(
            source='Withings',
            source_id='123456789',
            timestamp=timezone.make_aware(datetime(2023, 10, 25, 12, 0, 0)),
            weight_kg=74.0  # Old value
        )

        # Mock: API returns updated data for same measurement
        updated_data = {
            'status': 0,
            'body': {
                'measuregrps': [
                    {
                        'grpid': 123456789,
                        'date': 1698235200,
                        'measures': [
                            {'value': 75000, 'type': 1, 'unit': -3}  # Updated to 75.0 kg
                        ]
                    }
                ]
            }
        }
        mock_get_weight_measurements.return_value = updated_data

        # Run the sync command
        out = StringIO()
        call_command('sync_withings', days=7, stdout=out)

        # Assert: Still only 1 measurement (not duplicated)
        self.assertEqual(WeighIn.objects.count(), 1)

        # Assert: Measurement was updated with new value
        existing_weighin.refresh_from_db()
        self.assertEqual(existing_weighin.weight_kg, 75.0)

        # Assert: Command output shows update
        output = out.getvalue()
        self.assertIn('Created: 0', output)
        self.assertIn('Updated: 1', output)

    @mock.patch('weight.services.withings_client.WithingsAPIClient.get_weight_measurements')
    def test_sync_skips_non_weight_measurements(self, mock_get_weight_measurements):
        """Should skip measurements that aren't weight (type != 1)"""
        # Mock: API returns measurement with different type (e.g., body fat)
        mixed_data = {
            'status': 0,
            'body': {
                'measuregrps': [
                    {
                        'grpid': 123456789,
                        'date': 1698235200,
                        'measures': [
                            {'value': 75000, 'type': 1, 'unit': -3}  # Weight
                        ]
                    },
                    {
                        'grpid': 123456790,
                        'date': 1698148800,
                        'measures': [
                            {'value': 20000, 'type': 6, 'unit': -3}  # Body fat % (not weight)
                        ]
                    }
                ]
            }
        }
        mock_get_weight_measurements.return_value = mixed_data

        # Run the sync command
        out = StringIO()
        call_command('sync_withings', days=7, stdout=out)

        # Assert: Only weight measurement was saved
        self.assertEqual(WeighIn.objects.count(), 1)
        self.assertEqual(WeighIn.objects.first().source_id, '123456789')

        # Assert: Command output shows 1 skipped
        output = out.getvalue()
        self.assertIn('Skipped: 1', output)

    @mock.patch('weight.management.commands.sync_withings.WithingsAPIClient')
    def test_sync_raises_on_auth_error(self, mock_client_class):
        """Should raise exception when authentication fails (for sync_all to catch)"""
        # Mock: Client initialization and method call
        mock_client_instance = mock.Mock()
        mock_client_class.return_value = mock_client_instance

        # Mock: get_weight_measurements raises ValueError (expired refresh token)
        mock_client_instance.get_weight_measurements.side_effect = ValueError(
            "Withings refresh token expired or invalid. Please re-authenticate by running: "
            "python manage.py withings_auth"
        )

        # Assert: Command raises exception (not caught internally)
        out = StringIO()
        err = StringIO()
        with self.assertRaises(ValueError) as context:
            call_command('sync_withings', days=7, stdout=out, stderr=err)

        # Assert: Error message is preserved for sync_all to display
        error_message = str(context.exception)
        self.assertIn('Withings refresh token expired or invalid', error_message)
        self.assertIn('python manage.py withings_auth', error_message)

    @mock.patch('weight.services.withings_client.WithingsAPIClient.get_weight_measurements')
    def test_sync_handles_malformed_measurement_data(self, mock_get_weight_measurements):
        """Should skip measurements with missing required fields"""
        # Mock: API returns malformed measurement data
        malformed_data = {
            'status': 0,
            'body': {
                'measuregrps': [
                    {
                        'grpid': 123456789,
                        'date': 1698235200,
                        'measures': [
                            {'value': 75000, 'type': 1, 'unit': -3}  # Good
                        ]
                    },
                    {
                        # 'grpid': missing
                        'date': 1698148800,
                        'measures': [
                            {'value': 74500, 'type': 1, 'unit': -3}
                        ]
                    },
                    {
                        'grpid': 123456791,
                        # 'date': missing
                        'measures': [
                            {'value': 74000, 'type': 1, 'unit': -3}
                        ]
                    }
                ]
            }
        }
        mock_get_weight_measurements.return_value = malformed_data

        # Run the sync command
        out = StringIO()
        call_command('sync_withings', days=7, stdout=out)

        # Assert: Only valid measurement was saved
        self.assertEqual(WeighIn.objects.count(), 1)
        self.assertEqual(WeighIn.objects.first().source_id, '123456789')

        # Assert: Command output shows 2 skipped
        output = out.getvalue()
        self.assertIn('Skipped: 2', output)

    @mock.patch('weight.services.withings_client.WithingsAPIClient.get_weight_measurements')
    def test_sync_converts_units_correctly(self, mock_get_weight_measurements):
        """Should convert Withings units to kg correctly"""
        # Mock: Measurement with unit=-3 (multiply by 10^-3 to get kg)
        measurement_data = {
            'status': 0,
            'body': {
                'measuregrps': [
                    {
                        'grpid': 123456789,
                        'date': 1698235200,
                        'measures': [
                            {'value': 75500, 'type': 1, 'unit': -3}  # 75.500 kg
                        ]
                    }
                ]
            }
        }
        mock_get_weight_measurements.return_value = measurement_data

        # Run the sync command
        call_command('sync_withings', days=7, stdout=StringIO())

        # Assert: Weight calculated correctly
        weighin = WeighIn.objects.get(source_id='123456789')
        self.assertAlmostEqual(weighin.weight_kg, 75.5, places=3)
