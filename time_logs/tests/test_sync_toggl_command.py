"""
Phase 2 Tests: Sync Command

These tests validate the sync_toggl management command that fetches
time entries from Toggl API and saves them to the database.
"""
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from datetime import datetime
from unittest import mock
from io import StringIO

from time_logs.models import TimeLog
from projects.models import Project
from goals.models import Goal


class TestSyncTogglCommand(TestCase):
    """Test sync_toggl management command"""

    def setUp(self):
        """Set up test environment"""
        # Mock API credentials in database
        from oauth_integration.models import APICredential
        self.api_credential = APICredential.objects.create(
            provider='toggl',
            api_token='test_token',
            workspace_id='12345'
        )

        # Sample time entry data from Toggl API
        self.sample_time_entries = [
            {
                'id': 123456789,
                'start': '2023-10-25T10:00:00Z',
                'stop': '2023-10-25T12:00:00Z',
                'project_id': 999,
                'tags': ['coding', 'backend']
            },
            {
                'id': 123456790,
                'start': '2023-10-24T14:00:00Z',
                'stop': '2023-10-24T16:00:00Z',
                'project_id': 888,
                'tags': ['writing']
            }
        ]

        # Sample project data from Toggl API
        self.sample_projects = [
            {'id': 999, 'name': 'Web Development'},
            {'id': 888, 'name': 'Content Creation'}
        ]

    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_projects')
    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_time_entries')
    def test_sync_creates_new_time_logs(self, mock_get_entries, mock_get_projects):
        """Should create time log records from API data"""
        # Mock: API returns 2 time entries and projects
        mock_get_entries.return_value = self.sample_time_entries
        mock_get_projects.return_value = self.sample_projects

        # Run the sync command
        out = StringIO()
        call_command('sync_toggl', days=7, stdout=out)

        # Assert: 2 time logs created in database
        self.assertEqual(TimeLog.objects.count(), 2)

        # Assert: First time log saved correctly
        time_log1 = TimeLog.objects.get(source_id='123456789')
        self.assertEqual(time_log1.source, 'Toggl')
        self.assertEqual(time_log1.project_id, 999)

        # Assert: Start and end times parsed correctly (API returns UTC times)
        from datetime import timezone as dt_timezone
        expected_start = datetime(2023, 10, 25, 10, 0, 0, tzinfo=dt_timezone.utc)
        expected_end = datetime(2023, 10, 25, 12, 0, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(time_log1.start, expected_start)
        self.assertEqual(time_log1.end, expected_end)

        # Assert: Command output shows success
        output = out.getvalue()
        self.assertIn('Created: 2', output)
        self.assertIn('Found 2 time entries', output)

    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_projects')
    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_time_entries')
    def test_sync_updates_existing_time_logs(self, mock_get_entries, mock_get_projects):
        """Should update existing time logs using source_id, not create duplicates"""
        # Setup: Create existing time log in database
        existing_log = TimeLog.objects.create(
            source='Toggl',
            source_id='123456789',
            start=timezone.make_aware(datetime(2023, 10, 25, 9, 0, 0)),
            end=timezone.make_aware(datetime(2023, 10, 25, 11, 0, 0)),
            project_id=999
        )

        # Mock: API returns updated data for same entry
        mock_get_entries.return_value = [self.sample_time_entries[0]]
        mock_get_projects.return_value = [self.sample_projects[0]]

        # Run the sync command
        out = StringIO()
        call_command('sync_toggl', days=7, stdout=out)

        # Assert: Still only 1 time log (not duplicated)
        self.assertEqual(TimeLog.objects.count(), 1)

        # Assert: Time log was updated with new times (API returns UTC times)
        existing_log.refresh_from_db()
        from datetime import timezone as dt_timezone
        expected_start = datetime(2023, 10, 25, 10, 0, 0, tzinfo=dt_timezone.utc)
        expected_end = datetime(2023, 10, 25, 12, 0, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(existing_log.start, expected_start)
        self.assertEqual(existing_log.end, expected_end)

        # Assert: Command output shows update
        output = out.getvalue()
        self.assertIn('Created: 0', output)
        self.assertIn('Updated: 1', output)

    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_projects')
    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_time_entries')
    def test_sync_auto_creates_projects(self, mock_get_entries, mock_get_projects):
        """Should auto-create Project records from Toggl projects"""
        # Assert: No projects exist initially
        self.assertEqual(Project.objects.count(), 0)

        # Mock: API returns time entries with projects
        mock_get_entries.return_value = self.sample_time_entries
        mock_get_projects.return_value = self.sample_projects

        # Run the sync command
        call_command('sync_toggl', days=7, stdout=StringIO())

        # Assert: 2 projects auto-created
        self.assertEqual(Project.objects.count(), 2)

        # Assert: Project 999 created with correct name
        project1 = Project.objects.get(project_id=999)
        self.assertEqual(project1.display_string, 'Web Development')

        # Assert: Project 888 created
        project2 = Project.objects.get(project_id=888)
        self.assertEqual(project2.display_string, 'Content Creation')

    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_projects')
    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_time_entries')
    def test_sync_auto_creates_goals_from_tags(self, mock_get_entries, mock_get_projects):
        """Should auto-create Goal records from Toggl tags"""
        # Assert: No goals exist initially
        self.assertEqual(Goal.objects.count(), 0)

        # Mock: API returns time entries with tags
        mock_get_entries.return_value = self.sample_time_entries
        mock_get_projects.return_value = self.sample_projects

        # Run the sync command
        call_command('sync_toggl', days=7, stdout=StringIO())

        # Assert: 3 unique goals auto-created (coding, backend, writing)
        self.assertEqual(Goal.objects.count(), 3)

        # Assert: Goal 'coding' created
        goal1 = Goal.objects.get(goal_id='coding')
        self.assertEqual(goal1.display_string, 'coding')

        # Assert: ManyToMany relationship set correctly
        time_log1 = TimeLog.objects.get(source_id='123456789')
        goal_names = list(time_log1.goals.values_list('goal_id', flat=True))
        self.assertIn('coding', goal_names)
        self.assertIn('backend', goal_names)
        self.assertEqual(len(goal_names), 2)

    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_projects')
    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_time_entries')
    def test_sync_skips_entries_without_required_fields(self, mock_get_entries, mock_get_projects):
        """Should skip time entries missing required fields"""
        # Mock: API returns entries with missing fields
        malformed_entries = [
            {
                'id': 123456789,
                'start': '2023-10-25T10:00:00Z',
                'stop': '2023-10-25T12:00:00Z',
                'project_id': 999,
                'tags': []
            },
            {
                # Missing 'id'
                'start': '2023-10-24T10:00:00Z',
                'stop': '2023-10-24T12:00:00Z',
                'project_id': 888,
                'tags': []
            },
            {
                'id': 123456791,
                # Missing 'stop' (end time)
                'start': '2023-10-23T10:00:00Z',
                'project_id': 777,
                'tags': []
            },
            {
                'id': 123456792,
                'start': '2023-10-22T10:00:00Z',
                'stop': '2023-10-22T12:00:00Z',
                # Missing 'project_id' (required)
                'tags': []
            }
        ]
        mock_get_entries.return_value = malformed_entries
        mock_get_projects.return_value = self.sample_projects

        # Run the sync command
        out = StringIO()
        call_command('sync_toggl', days=7, stdout=out)

        # Assert: Only valid entry was saved
        self.assertEqual(TimeLog.objects.count(), 1)
        self.assertEqual(TimeLog.objects.first().source_id, '123456789')

        # Assert: Command output shows 3 skipped
        output = out.getvalue()
        self.assertIn('Skipped: 3', output)

    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_projects')
    @mock.patch('time_logs.services.toggl_client.TogglAPIClient.get_time_entries')
    def test_sync_handles_entries_without_tags(self, mock_get_entries, mock_get_projects):
        """Should handle time entries without tags (goals are optional)"""
        # Mock: API returns entry with no tags
        entry_without_tags = {
            'id': 123456789,
            'start': '2023-10-25T10:00:00Z',
            'stop': '2023-10-25T12:00:00Z',
            'project_id': 999,
            'tags': []  # No tags
        }
        mock_get_entries.return_value = [entry_without_tags]
        mock_get_projects.return_value = [self.sample_projects[0]]

        # Run the sync command
        call_command('sync_toggl', days=7, stdout=StringIO())

        # Assert: Time log created successfully
        self.assertEqual(TimeLog.objects.count(), 1)

        # Assert: No goals associated
        time_log = TimeLog.objects.first()
        self.assertEqual(time_log.goals.count(), 0)

    @mock.patch('time_logs.management.commands.sync_toggl.TogglAPIClient')
    def test_sync_raises_on_missing_credentials(self, mock_client_class):
        """Should raise exception when API credentials are missing"""
        # Mock: Client initialization fails
        mock_client_class.side_effect = ValueError(
            "TOGGL_API_TOKEN must be set in environment variables"
        )

        # Assert: Command raises exception
        out = StringIO()
        err = StringIO()
        with self.assertRaises(ValueError) as context:
            call_command('sync_toggl', days=7, stdout=out, stderr=err)

        # Assert: Error message is clear
        error_message = str(context.exception)
        self.assertIn('TOGGL_API_TOKEN', error_message)
