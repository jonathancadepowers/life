from django.test import TestCase, Client
from django.utils import timezone
from django.db import IntegrityError
from django.urls import reverse
from datetime import timedelta
from unittest import mock

from oauth_integration.models import OAuthCredential, APICredential


class OAuthCredentialModelTests(TestCase):
    """Tests for the OAuthCredential model."""

    def test_create_credential_with_required_fields(self):
        """Create credential with required fields."""
        cred = OAuthCredential.objects.create(
            provider='whoop',
            client_id='test-client-id',
            client_secret='test-client-secret',
            redirect_uri='http://localhost/callback',
        )
        self.assertEqual(cred.provider, 'whoop')
        self.assertEqual(cred.client_id, 'test-client-id')
        self.assertEqual(cred.client_secret, 'test-client-secret')
        self.assertEqual(cred.redirect_uri, 'http://localhost/callback')

    def test_str_returns_provider_oauth_credentials(self):
        """__str__ returns 'Provider OAuth Credentials'."""
        cred = OAuthCredential.objects.create(
            provider='whoop',
            client_id='cid',
            client_secret='csecret',
            redirect_uri='http://localhost/callback',
        )
        self.assertEqual(str(cred), 'Whoop OAuth Credentials')

    def test_is_token_expired_true_when_in_past(self):
        """is_token_expired() returns True when token_expires_at is in the past."""
        cred = OAuthCredential.objects.create(
            provider='whoop',
            client_id='cid',
            client_secret='csecret',
            redirect_uri='http://localhost/callback',
            token_expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(cred.is_token_expired())

    def test_is_token_expired_true_when_none(self):
        """is_token_expired() returns True when token_expires_at is None."""
        cred = OAuthCredential.objects.create(
            provider='whoop',
            client_id='cid',
            client_secret='csecret',
            redirect_uri='http://localhost/callback',
            token_expires_at=None,
        )
        self.assertTrue(cred.is_token_expired())

    def test_is_token_expired_false_when_in_future(self):
        """is_token_expired() returns False when token_expires_at is in the future."""
        cred = OAuthCredential.objects.create(
            provider='whoop',
            client_id='cid',
            client_secret='csecret',
            redirect_uri='http://localhost/callback',
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertFalse(cred.is_token_expired())

    def test_update_tokens_with_access_token_only(self):
        """update_tokens() with just access_token updates only the access token."""
        cred = OAuthCredential.objects.create(
            provider='whoop',
            client_id='cid',
            client_secret='csecret',
            redirect_uri='http://localhost/callback',
            refresh_token='original-refresh',
        )
        cred.update_tokens(access_token='new-access-token')
        cred.refresh_from_db()
        self.assertEqual(cred.access_token, 'new-access-token')
        self.assertEqual(cred.refresh_token, 'original-refresh')

    def test_update_tokens_with_access_and_refresh(self):
        """update_tokens() with access_token + refresh_token updates both."""
        cred = OAuthCredential.objects.create(
            provider='whoop',
            client_id='cid',
            client_secret='csecret',
            redirect_uri='http://localhost/callback',
        )
        cred.update_tokens(access_token='new-access', refresh_token='new-refresh')
        cred.refresh_from_db()
        self.assertEqual(cred.access_token, 'new-access')
        self.assertEqual(cred.refresh_token, 'new-refresh')

    def test_update_tokens_with_expires_in_sets_expiry(self):
        """update_tokens() with expires_in sets token_expires_at."""
        cred = OAuthCredential.objects.create(
            provider='whoop',
            client_id='cid',
            client_secret='csecret',
            redirect_uri='http://localhost/callback',
        )
        before = timezone.now()
        cred.update_tokens(access_token='token', expires_in=3600)
        cred.refresh_from_db()
        self.assertIsNotNone(cred.token_expires_at)
        # Should be approximately 1 hour from now
        expected = before + timedelta(seconds=3600)
        self.assertAlmostEqual(
            cred.token_expires_at.timestamp(),
            expected.timestamp(),
            delta=5,  # 5-second tolerance
        )

    def test_provider_unique_constraint(self):
        """Provider field has a unique constraint."""
        OAuthCredential.objects.create(
            provider='whoop',
            client_id='cid1',
            client_secret='csecret1',
            redirect_uri='http://localhost/callback1',
        )
        with self.assertRaises(IntegrityError):
            OAuthCredential.objects.create(
                provider='whoop',
                client_id='cid2',
                client_secret='csecret2',
                redirect_uri='http://localhost/callback2',
            )


class APICredentialModelTests(TestCase):
    """Tests for the APICredential model."""

    def test_create_credential_with_required_fields(self):
        """Create credential with required fields."""
        cred = APICredential.objects.create(
            provider='toggl',
            api_token='test-api-token',
        )
        self.assertEqual(cred.provider, 'toggl')
        self.assertEqual(cred.api_token, 'test-api-token')

    def test_str_returns_provider_api_credentials(self):
        """__str__ returns 'Provider API Credentials'."""
        cred = APICredential.objects.create(
            provider='toggl',
            api_token='test-api-token',
        )
        self.assertEqual(str(cred), 'Toggl API Credentials')

    def test_provider_unique_constraint(self):
        """Provider field has a unique constraint."""
        APICredential.objects.create(
            provider='toggl',
            api_token='token1',
        )
        with self.assertRaises(IntegrityError):
            APICredential.objects.create(
                provider='toggl',
                api_token='token2',
            )

    def test_default_empty_metadata(self):
        """Default metadata is an empty dict."""
        cred = APICredential.objects.create(
            provider='toggl',
            api_token='test-api-token',
        )
        self.assertEqual(cred.metadata, {})


class WhoopOAuthViewTests(TestCase):
    """Tests for Whoop OAuth views."""

    def setUp(self):
        self.client = Client()

    @mock.patch('workouts.services.whoop_client.WhoopAPIClient')
    def test_whoop_authorize_redirects(self, MockWhoopClient):
        """GET whoop_authorize redirects (302) and sets session state."""
        mock_instance = MockWhoopClient.return_value
        mock_instance.get_authorization_url.return_value = 'https://api.whoop.com/auth?state=abc'

        response = self.client.get(reverse('oauth_integration:whoop_authorize'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('https://api.whoop.com/auth', response.url)

        # Session should have the state
        session = self.client.session
        self.assertIn('whoop_oauth_state', session)

    @mock.patch('workouts.services.whoop_client.WhoopAPIClient')
    def test_whoop_callback_with_valid_code_and_state(self, MockWhoopClient):
        """GET whoop_callback with code and valid state redirects with success."""
        mock_instance = MockWhoopClient.return_value
        mock_instance.exchange_code_for_token.return_value = None

        # Set session state
        session = self.client.session
        session['whoop_oauth_state'] = 'test_state'
        session.save()

        response = self.client.get(
            reverse('oauth_integration:whoop_callback'),
            {'code': 'auth_code', 'state': 'test_state'},
        )
        self.assertEqual(response.status_code, 302)
        mock_instance.exchange_code_for_token.assert_called_once_with('auth_code')

    @mock.patch('workouts.services.whoop_client.WhoopAPIClient')
    def test_whoop_callback_without_code_redirects_with_error(self, MockWhoopClient):
        """GET whoop_callback without code redirects with error."""
        response = self.client.get(reverse('oauth_integration:whoop_callback'))
        self.assertEqual(response.status_code, 302)

    @mock.patch('workouts.services.whoop_client.WhoopAPIClient')
    def test_whoop_callback_with_wrong_state_redirects_with_error(self, MockWhoopClient):
        """GET whoop_callback with wrong state redirects with error."""
        mock_instance = MockWhoopClient.return_value

        session = self.client.session
        session['whoop_oauth_state'] = 'correct_state'
        session.save()

        response = self.client.get(
            reverse('oauth_integration:whoop_callback'),
            {'code': 'auth_code', 'state': 'wrong_state'},
        )
        self.assertEqual(response.status_code, 302)
        # exchange_code_for_token should NOT be called
        mock_instance.exchange_code_for_token.assert_not_called()


class WithingsOAuthViewTests(TestCase):
    """Tests for Withings OAuth views."""

    def setUp(self):
        self.client = Client()

    @mock.patch('weight.services.withings_client.WithingsAPIClient')
    def test_withings_authorize_redirects(self, MockWithingsClient):
        """GET withings_authorize redirects (302) and sets session state."""
        mock_instance = MockWithingsClient.return_value
        mock_instance.get_authorization_url.return_value = 'https://account.withings.com/oauth2?state=xyz'

        response = self.client.get(reverse('oauth_integration:withings_authorize'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('https://account.withings.com/oauth2', response.url)

        session = self.client.session
        self.assertIn('withings_oauth_state', session)

    @mock.patch('weight.services.withings_client.WithingsAPIClient')
    def test_withings_callback_with_valid_code_and_state(self, MockWithingsClient):
        """GET withings_callback with code and valid state redirects with success."""
        mock_instance = MockWithingsClient.return_value
        mock_instance.exchange_code_for_token.return_value = None

        session = self.client.session
        session['withings_oauth_state'] = 'test_state'
        session.save()

        response = self.client.get(
            reverse('oauth_integration:withings_callback'),
            {'code': 'auth_code', 'state': 'test_state'},
        )
        self.assertEqual(response.status_code, 302)
        mock_instance.exchange_code_for_token.assert_called_once_with('auth_code')

    @mock.patch('weight.services.withings_client.WithingsAPIClient')
    def test_withings_callback_without_code_redirects_with_error(self, MockWithingsClient):
        """GET withings_callback without code redirects with error."""
        response = self.client.get(reverse('oauth_integration:withings_callback'))
        self.assertEqual(response.status_code, 302)

    @mock.patch('weight.services.withings_client.WithingsAPIClient')
    def test_withings_callback_with_wrong_state_redirects_with_error(self, MockWithingsClient):
        """GET withings_callback with wrong state redirects with error."""
        mock_instance = MockWithingsClient.return_value

        session = self.client.session
        session['withings_oauth_state'] = 'correct_state'
        session.save()

        response = self.client.get(
            reverse('oauth_integration:withings_callback'),
            {'code': 'auth_code', 'state': 'wrong_state'},
        )
        self.assertEqual(response.status_code, 302)
        mock_instance.exchange_code_for_token.assert_not_called()
