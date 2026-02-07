"""
Phase 3 Tests: Robustness & Error Handling

These tests validate edge cases, fallback mechanisms, and error handling
to ensure the Whoop integration is resilient to various failure modes.
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from unittest import mock
import requests

from oauth_integration.models import OAuthCredential
from workouts.services.whoop_client import WhoopAPIClient


class TestWhoopRobustness(TestCase):
    """Test robustness and error handling"""

    def setUp(self):
        """Set up test database with OAuth credentials"""
        self.credential = OAuthCredential.objects.create(
            provider='whoop',
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='http://localhost:8000/whoop/callback',
            access_token='valid_access_token',
            refresh_token='valid_refresh_token',
            token_expires_at=timezone.now() + timedelta(hours=1)
        )

    def test_reactive_refresh_on_401_error(self):
        """Should refresh token when API returns 401, even if proactive check missed it"""
        # Scenario: Token expires between proactive check and API call
        # This tests the fallback 401 handler

        client = WhoopAPIClient()

        # Mock: First API call returns 401 (expired token)
        mock_401_response = mock.Mock()
        mock_401_response.status_code = 401
        mock_401_response.json.return_value = {'error': 'unauthorized'}

        # Mock: Token refresh succeeds
        mock_refresh_response = mock.Mock()
        mock_refresh_response.status_code = 200
        mock_refresh_response.json.return_value = {
            'access_token': 'refreshed_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 3600
        }

        # Mock: Retry with new token succeeds
        mock_success_response = mock.Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {'records': []}

        with mock.patch('requests.post', return_value=mock_refresh_response):
            with mock.patch('requests.request', side_effect=[mock_401_response, mock_success_response]) as mock_request:
                # Make API request
                client._make_authenticated_request('/developer/v1/activity/workout')

                # Assert: Two API requests made (first 401, second success)
                self.assertEqual(mock_request.call_count, 2)

                # Assert: Second request used new token
                second_call_headers = mock_request.call_args_list[1][1]['headers']
                self.assertEqual(second_call_headers['Authorization'], 'Bearer refreshed_access_token')

                # Assert: New token saved to database
                self.credential.refresh_from_db()
                self.assertEqual(self.credential.access_token, 'refreshed_access_token')

    def test_refresh_token_rotation(self):
        """Should update refresh token if Whoop provides a new one (token rotation)"""
        # Many OAuth providers rotate refresh tokens for security
        # Each refresh gives you a new refresh token, invalidating the old one

        client = WhoopAPIClient()

        # Mock: Token refresh returns NEW refresh token (rotation)
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'rotated_refresh_token',  # NEW refresh token
            'expires_in': 3600
        }

        with mock.patch('requests.post', return_value=mock_response):
            # Refresh the token
            client.refresh_access_token()

            # Assert: Both access and refresh tokens updated
            self.credential.refresh_from_db()
            self.assertEqual(self.credential.access_token, 'new_access_token')
            self.assertEqual(self.credential.refresh_token, 'rotated_refresh_token')

    def test_network_error_handling(self):
        """Should raise clear error on network failure"""
        client = WhoopAPIClient()

        # Mock: Network timeout
        with mock.patch('requests.request', side_effect=requests.exceptions.Timeout('Connection timeout')):
            # Assert: Timeout exception raised
            with self.assertRaises(requests.exceptions.Timeout):
                client._make_authenticated_request('/developer/v1/activity/workout')

        # Mock: Connection error
        with mock.patch('requests.request', side_effect=requests.exceptions.ConnectionError('Failed to connect')):
            # Assert: Connection exception raised
            with self.assertRaises(requests.exceptions.ConnectionError):
                client._make_authenticated_request('/developer/v1/activity/workout')

    def test_invalid_api_response_handling(self):
        """Should handle malformed API responses gracefully"""
        client = WhoopAPIClient()

        # Mock: API returns invalid JSON
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError('Invalid JSON')

        with mock.patch('requests.request', return_value=mock_response):
            # Assert: JSON parsing error raised
            with self.assertRaises(ValueError):
                client._make_authenticated_request('/developer/v1/activity/workout')

    def test_missing_credentials_error(self):
        """Should raise clear error when no credentials available"""
        # Setup: Delete credentials from database
        self.credential.delete()

        # Clear environment variables (simulate no fallback)
        with mock.patch.dict('os.environ', {}, clear=True):
            # Assert: ValueError raised with clear message
            with self.assertRaises(ValueError) as context:
                WhoopAPIClient()

            error_message = str(context.exception)
            self.assertIn('client_id', error_message.lower())

    def test_api_rate_limiting(self):
        """Should handle 429 rate limit errors appropriately"""
        client = WhoopAPIClient()

        # Mock: API returns 429 (rate limited)
        mock_429_response = mock.Mock()
        mock_429_response.status_code = 429
        mock_429_response.json.return_value = {'error': 'rate_limit_exceeded'}
        mock_429_response.headers = {'Retry-After': '60'}
        mock_429_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            '429 Client Error: Too Many Requests', response=mock_429_response
        )

        with mock.patch('requests.request', return_value=mock_429_response):
            # Assert: HTTPError raised (429 is not automatically retried)
            with self.assertRaises(requests.exceptions.HTTPError) as context:
                client._make_authenticated_request('/developer/v1/activity/workout')

            # Assert: Status code is 429
            self.assertEqual(context.exception.response.status_code, 429)

    def test_server_error_handling(self):
        """Should handle 5xx server errors from Whoop API"""
        client = WhoopAPIClient()

        # Mock: API returns 500 (server error)
        mock_500_response = mock.Mock()
        mock_500_response.status_code = 500
        mock_500_response.json.return_value = {'error': 'internal_server_error'}
        mock_500_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            '500 Server Error: Internal Server Error', response=mock_500_response
        )

        with mock.patch('requests.request', return_value=mock_500_response):
            # Assert: HTTPError raised
            with self.assertRaises(requests.exceptions.HTTPError) as context:
                client._make_authenticated_request('/developer/v1/activity/workout')

            # Assert: Status code is 500
            self.assertEqual(context.exception.response.status_code, 500)

    def test_token_refresh_without_new_refresh_token(self):
        """Should handle refresh response that doesn't include new refresh token"""
        # Some OAuth providers don't rotate refresh tokens
        # They only return a new access token

        client = WhoopAPIClient()
        old_refresh_token = self.credential.refresh_token

        # Mock: Token refresh returns only access token (no new refresh token)
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            # 'refresh_token': not included
            'expires_in': 3600
        }

        with mock.patch('requests.post', return_value=mock_response):
            # Refresh the token
            client.refresh_access_token()

            # Assert: Access token updated
            self.credential.refresh_from_db()
            self.assertEqual(self.credential.access_token, 'new_access_token')

            # Assert: Refresh token unchanged (kept the old one)
            self.assertEqual(self.credential.refresh_token, old_refresh_token)

    def test_double_401_error_not_infinite_loop(self):
        """Should not infinitely retry if token refresh fails to resolve 401"""
        # Edge case: Token refresh succeeds but new token is still invalid
        # Should fail after one retry, not infinite loop

        client = WhoopAPIClient()

        # Mock: Token refresh succeeds
        mock_refresh_response = mock.Mock()
        mock_refresh_response.status_code = 200
        mock_refresh_response.json.return_value = {
            'access_token': 'new_but_still_invalid_token',
            'expires_in': 3600
        }

        # Mock: API returns 401 BOTH times (even after refresh)
        mock_401_response = mock.Mock()
        mock_401_response.status_code = 401
        mock_401_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            '401 Client Error: Unauthorized', response=mock_401_response
        )

        with mock.patch('requests.post', return_value=mock_refresh_response):
            with mock.patch('requests.request', return_value=mock_401_response) as mock_request:
                # Assert: HTTPError raised (not infinite loop)
                with self.assertRaises(requests.exceptions.HTTPError):
                    client._make_authenticated_request('/developer/v1/activity/workout')

                # Assert: Only 2 API requests made (original + 1 retry)
                self.assertEqual(mock_request.call_count, 2)

    def test_empty_api_response(self):
        """Should handle empty/null responses from API gracefully"""
        client = WhoopAPIClient()

        # Mock: API returns empty response
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = None

        with mock.patch('requests.request', return_value=mock_response):
            # Should not crash, just return None
            result = client._make_authenticated_request('/developer/v1/activity/workout')
            self.assertIsNone(result)

    def test_token_expires_at_edge_cases(self):
        """Should handle edge cases in token expiration calculation"""
        # Test: Expiration exactly now
        self.credential.token_expires_at = timezone.now()
        self.credential.save()

        # Should be considered expired
        self.assertTrue(self.credential.is_token_expired())

        # Test: Expiration 1 second from now
        self.credential.token_expires_at = timezone.now() + timedelta(seconds=1)
        self.credential.save()

        # Should NOT be considered expired
        self.assertFalse(self.credential.is_token_expired())

        # Test: Expiration 1 second ago
        self.credential.token_expires_at = timezone.now() - timedelta(seconds=1)
        self.credential.save()

        # Should be considered expired
        self.assertTrue(self.credential.is_token_expired())
