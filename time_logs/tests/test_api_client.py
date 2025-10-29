"""
Phase 1 Tests: API Client

These tests validate the TogglAPIClient basic authentication and API request handling.
"""
from django.test import TestCase
from unittest import mock
import requests

from time_logs.services.toggl_client import TogglAPIClient


class TestTogglAPIClient(TestCase):
    """Test Toggl API client basic functionality"""

    def test_missing_api_token_error(self):
        """Should raise clear error when API token is missing"""
        # Clear environment variables
        with mock.patch.dict('os.environ', {}, clear=True):
            # Assert: ValueError raised with clear message
            with self.assertRaises(ValueError) as context:
                TogglAPIClient()

            error_message = str(context.exception)
            self.assertIn('TOGGL_API_TOKEN', error_message)

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    def test_successful_authentication(self, mock_getenv):
        """Should use API token for basic auth"""
        # Mock: Environment variables set
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_api_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Create client
        client = TogglAPIClient()

        # Assert: Client initialized with correct credentials
        self.assertEqual(client.api_token, 'test_api_token')
        self.assertEqual(client.workspace_id, '12345')

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_make_request_uses_basic_auth(self, mock_request, mock_getenv):
        """Should use API token as username with 'api_token' as password"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token_123',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: Successful API response
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'success'}
        mock_request.return_value = mock_response

        # Make API request
        client = TogglAPIClient()
        result = client._make_request('/me/time_entries')

        # Assert: Request used correct basic auth
        call_args = mock_request.call_args
        auth_tuple = call_args[1]['auth']
        self.assertEqual(auth_tuple, ('test_token_123', 'api_token'))

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_http_401_error(self, mock_request, mock_getenv):
        """Should raise HTTPError on 401 (invalid API token)"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'invalid_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: 401 response
        mock_response = mock.Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            '401 Client Error: Unauthorized', response=mock_response
        )
        mock_request.return_value = mock_response

        # Assert: HTTPError raised
        client = TogglAPIClient()
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            client._make_request('/me/time_entries')

        self.assertEqual(context.exception.response.status_code, 401)

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.post')
    @mock.patch('requests.request')
    def test_get_time_entries_success(self, mock_request, mock_post, mock_getenv):
        """Should fetch time entries with date range parameters"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: API returns grouped time entries (new Reports API format)
        mock_post_response = mock.Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = [
            {
                'project_id': 999,
                'tag_ids': [1, 2],
                'time_entries': [
                    {
                        'id': 123456789,
                        'start': '2023-10-25T10:00:00Z',
                        'stop': '2023-10-25T12:00:00Z',
                        'seconds': 7200
                    }
                ]
            }
        ]
        mock_post.return_value = mock_post_response

        # Mock: get_tags() and get_current_time_entry() responses
        mock_request_response = mock.Mock()
        mock_request_response.status_code = 200
        mock_request_response.json.return_value = [
            {'id': 1, 'name': 'coding'},
            {'id': 2, 'name': 'backend'}
        ]
        mock_request.return_value = mock_request_response

        # Fetch time entries
        client = TogglAPIClient()
        from datetime import datetime
        entries = client.get_time_entries(
            start_date=datetime(2023, 10, 1),
            end_date=datetime(2023, 10, 31)
        )

        # Assert: Returns list of entries
        self.assertIsInstance(entries, list)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['id'], 123456789)
        self.assertEqual(entries[0]['tags'], ['coding', 'backend'])

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_get_projects_success(self, mock_request, mock_getenv):
        """Should fetch projects from workspace"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: API returns projects
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'id': 100, 'name': 'Project Alpha'},
            {'id': 200, 'name': 'Project Beta'}
        ]
        mock_request.return_value = mock_response

        # Fetch projects
        client = TogglAPIClient()
        projects = client.get_projects()

        # Assert: Returns list of projects
        self.assertIsInstance(projects, list)
        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0]['name'], 'Project Alpha')

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    def test_get_projects_missing_workspace_id(self, mock_getenv):
        """Should raise error when workspace_id is missing"""
        # Mock: API token set but workspace_id missing
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': None
        }.get(key)

        # Create client
        client = TogglAPIClient()

        # Assert: ValueError raised
        with self.assertRaises(ValueError) as context:
            client.get_projects()

        error_message = str(context.exception)
        self.assertIn('TOGGL_WORKSPACE_ID', error_message)
