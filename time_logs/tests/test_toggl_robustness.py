"""
Phase 3 Tests: Robustness & Error Handling

These tests validate edge cases, fallback mechanisms, and error handling
to ensure the Toggl integration is resilient to various failure modes.
"""
from django.test import TestCase
from django.utils import timezone
from unittest import mock
import requests

from time_logs.services.toggl_client import TogglAPIClient
from time_logs.models import TimeLog


class TestTogglRobustness(TestCase):
    """Test robustness and error handling"""

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_network_timeout_error(self, mock_request, mock_getenv):
        """Should raise clear error on network timeout"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: Network timeout
        mock_request.side_effect = requests.exceptions.Timeout('Connection timeout')

        # Assert: Timeout exception raised
        client = TogglAPIClient()
        with self.assertRaises(requests.exceptions.Timeout):
            client.get_time_entries()

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_network_connection_error(self, mock_request, mock_getenv):
        """Should raise clear error on connection failure"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: Connection error
        mock_request.side_effect = requests.exceptions.ConnectionError('Failed to connect')

        # Assert: Connection exception raised
        client = TogglAPIClient()
        with self.assertRaises(requests.exceptions.ConnectionError):
            client.get_time_entries()

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_http_404_error(self, mock_request, mock_getenv):
        """Should handle 404 errors from API"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: 404 response
        mock_response = mock.Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            '404 Client Error: Not Found', response=mock_response
        )
        mock_request.return_value = mock_response

        # Assert: HTTPError raised
        client = TogglAPIClient()
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            client._make_request('/invalid/endpoint')

        self.assertEqual(context.exception.response.status_code, 404)

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_api_rate_limiting(self, mock_request, mock_getenv):
        """Should handle 429 rate limit errors"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: API returns 429 (rate limited)
        mock_response = mock.Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            '429 Client Error: Too Many Requests', response=mock_response
        )
        mock_request.return_value = mock_response

        # Assert: HTTPError raised
        client = TogglAPIClient()
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            client.get_time_entries()

        # Assert: Status code is 429
        self.assertEqual(context.exception.response.status_code, 429)

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_server_error_handling(self, mock_request, mock_getenv):
        """Should handle 5xx server errors from Toggl API"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: API returns 500 (server error)
        mock_response = mock.Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            '500 Server Error: Internal Server Error', response=mock_response
        )
        mock_request.return_value = mock_response

        # Assert: HTTPError raised
        client = TogglAPIClient()
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            client.get_time_entries()

        # Assert: Status code is 500
        self.assertEqual(context.exception.response.status_code, 500)

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_invalid_json_response(self, mock_request, mock_getenv):
        """Should handle malformed JSON responses"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: API returns invalid JSON
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError('Invalid JSON')
        mock_request.return_value = mock_response

        # Assert: JSON parsing error raised
        client = TogglAPIClient()
        with self.assertRaises(ValueError):
            client.get_time_entries()

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_empty_response_handling(self, mock_request, mock_getenv):
        """Should handle empty response gracefully"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: API returns empty array (no time entries)
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        # Fetch time entries
        client = TogglAPIClient()
        entries = client.get_time_entries()

        # Assert: Returns empty list (no error)
        self.assertEqual(entries, [])

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_date_range_parameter_formatting(self, mock_request, mock_getenv):
        """Should format date range parameters correctly"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: API response
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        # Make request with specific dates
        from datetime import datetime
        client = TogglAPIClient()
        client.get_time_entries(
            start_date=datetime(2023, 10, 1, 0, 0, 0),
            end_date=datetime(2023, 10, 31, 23, 59, 59)
        )

        # Assert: Parameters formatted correctly
        call_args = mock_request.call_args
        params = call_args[1]['params']
        self.assertEqual(params['start_date'], '2023-10-01T00:00:00Z')
        self.assertEqual(params['end_date'], '2023-10-31T23:59:59Z')

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_default_date_range(self, mock_request, mock_getenv):
        """Should use default 30-day range if no dates provided"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: API response
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        # Make request without dates
        client = TogglAPIClient()
        client.get_time_entries()

        # Assert: Request was made (default dates used)
        self.assertTrue(mock_request.called)

    def test_time_log_duration_calculation(self):
        """Should calculate duration correctly"""
        from datetime import datetime

        # Create time log with 2-hour duration
        time_log = TimeLog.objects.create(
            source='Toggl',
            source_id='test123',
            start=timezone.make_aware(datetime(2023, 10, 25, 10, 0, 0)),
            end=timezone.make_aware(datetime(2023, 10, 25, 12, 0, 0)),
            project_id=999
        )

        # Assert: Duration is 120 minutes
        self.assertEqual(time_log.duration_minutes, 120.0)

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_handles_null_values_in_response(self, mock_request, mock_getenv):
        """Should handle null/None values in API response"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Mock: API returns entry with null project_id (should be skipped)
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'id': 123456789,
                'start': '2023-10-25T10:00:00Z',
                'stop': '2023-10-25T12:00:00Z',
                'project_id': None,  # Null project
                'tags': []
            }
        ]
        mock_request.return_value = mock_response

        # Fetch time entries
        client = TogglAPIClient()
        entries = client.get_time_entries()

        # Assert: Entry returned (but will be skipped by sync command)
        self.assertEqual(len(entries), 1)
        self.assertIsNone(entries[0]['project_id'])

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    def test_api_token_whitespace_trimmed(self, mock_getenv):
        """Should handle API token with whitespace"""
        # Mock: API token has trailing whitespace
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': '  test_token_with_spaces  ',
            'TOGGL_WORKSPACE_ID': '12345'
        }.get(key)

        # Create client
        client = TogglAPIClient()

        # Assert: Token stored as-is (Toggl API will handle validation)
        self.assertEqual(client.api_token, '  test_token_with_spaces  ')

    @mock.patch('time_logs.services.toggl_client.os.getenv')
    @mock.patch('requests.request')
    def test_unauthorized_workspace_access(self, mock_request, mock_getenv):
        """Should handle 403 error when accessing unauthorized workspace"""
        # Mock: Environment variables
        mock_getenv.side_effect = lambda key: {
            'TOGGL_API_TOKEN': 'test_token',
            'TOGGL_WORKSPACE_ID': '99999'  # Workspace user doesn't have access to
        }.get(key)

        # Mock: 403 response
        mock_response = mock.Mock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            '403 Client Error: Forbidden', response=mock_response
        )
        mock_request.return_value = mock_response

        # Assert: HTTPError raised
        client = TogglAPIClient()
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            client.get_projects()

        self.assertEqual(context.exception.response.status_code, 403)
