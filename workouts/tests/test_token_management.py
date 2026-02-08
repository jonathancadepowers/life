"""
Phase 1 Critical Tests: Token Management

These tests validate the OAuth token refresh logic that ensures
the Whoop integration remains functional as tokens expire.
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from unittest import mock

from oauth_integration.models import OAuthCredential
from workouts.services.whoop_client import WhoopAPIClient


class TestWhoopTokenManagement(TestCase):
    """Test OAuth token handling and refresh logic"""

    def setUp(self):
        """Set up test database with OAuth credentials"""
        self.credential = OAuthCredential.objects.create(
            provider="whoop",
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8000/whoop/callback",
            access_token="old_access_token",
            refresh_token="valid_refresh_token",
            token_expires_at=timezone.now() + timedelta(hours=1),  # Valid token
        )

    def test_expired_refresh_token_error_message(self):
        """Should raise clear error when refresh token expires (400 from Whoop)"""
        # Setup: Create client with expired access token
        self.credential.token_expires_at = timezone.now() - timedelta(hours=1)
        self.credential.save()

        client = WhoopAPIClient()

        # Mock: Whoop returns 400 on token refresh (expired refresh token)
        mock_response = mock.Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "invalid_grant"}

        with mock.patch("requests.post", return_value=mock_response):
            # Assert: Raises ValueError with clear message
            with self.assertRaises(ValueError) as context:
                client.refresh_access_token()

            error_message = str(context.exception)
            self.assertIn("Whoop refresh token expired or invalid", error_message)
            self.assertIn("python manage.py whoop_auth", error_message)

    def test_proactive_token_refresh_when_expired(self):
        """Should refresh token before making API call if database shows it's expired"""
        # Setup: Create expired token in database
        self.credential.access_token = "expired_access_token"
        self.credential.token_expires_at = timezone.now() - timedelta(hours=1)
        self.credential.save()

        client = WhoopAPIClient()

        # Mock: Token refresh returns new token
        mock_refresh_response = mock.Mock()
        mock_refresh_response.status_code = 200
        mock_refresh_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }

        # Mock: API request succeeds with new token
        mock_api_response = mock.Mock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {"records": []}

        with mock.patch("requests.post", return_value=mock_refresh_response):
            with mock.patch("requests.request", return_value=mock_api_response) as mock_request:
                # Make an API request (this should trigger proactive refresh)
                client._make_authenticated_request("/developer/v1/activity/workout")

                # Assert: Token was refreshed before API call
                self.credential.refresh_from_db()
                self.assertEqual(self.credential.access_token, "new_access_token")

                # Assert: API request used new token
                call_args = mock_request.call_args
                headers = call_args[1]["headers"]
                self.assertEqual(headers["Authorization"], "Bearer new_access_token")

    def test_auto_recovery_when_access_token_missing(self):
        """Should use refresh token to get new access token if access token is missing"""
        # Setup: Database has refresh token but no access token
        self.credential.access_token = ""  # Missing
        self.credential.refresh_token = "valid_refresh_token"
        self.credential.save()

        client = WhoopAPIClient()

        # Mock: Token refresh succeeds
        mock_refresh_response = mock.Mock()
        mock_refresh_response.status_code = 200
        mock_refresh_response.json.return_value = {
            "access_token": "recovered_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }

        # Mock: API request succeeds
        mock_api_response = mock.Mock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {"records": []}

        with mock.patch("requests.post", return_value=mock_refresh_response):
            with mock.patch("requests.request", return_value=mock_api_response):
                # Make an API request (should auto-recover)
                client._make_authenticated_request("/developer/v1/activity/workout")

                # Assert: Access token obtained and saved
                self.credential.refresh_from_db()
                self.assertEqual(self.credential.access_token, "recovered_access_token")

    def test_saves_tokens_to_database_after_refresh(self):
        """Should persist refreshed tokens to database"""
        # Setup: Client with valid refresh token
        client = WhoopAPIClient()

        # Mock: Successful token refresh with new refresh token (token rotation)
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "brand_new_access_token",
            "refresh_token": "brand_new_refresh_token",  # Whoop rotates refresh tokens
            "expires_in": 3600,
        }

        with mock.patch("requests.post", return_value=mock_response):
            # Refresh the token
            client.refresh_access_token()

            # Assert: New tokens saved to database
            self.credential.refresh_from_db()
            self.assertEqual(self.credential.access_token, "brand_new_access_token")
            self.assertEqual(self.credential.refresh_token, "brand_new_refresh_token")

            # Assert: Expiration time updated (should be ~1 hour from now)
            time_until_expiry = self.credential.token_expires_at - timezone.now()
            self.assertGreater(time_until_expiry.total_seconds(), 3500)  # ~58+ minutes
            self.assertLess(time_until_expiry.total_seconds(), 3700)  # ~61- minutes
