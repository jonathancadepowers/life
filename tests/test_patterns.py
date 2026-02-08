"""
Pattern tests — executable documentation of the codebase's critical invariants.

These tests exist to demonstrate (and enforce) the patterns that every developer
or AI session must follow when extending the codebase. Read these before writing
new code.

Run with: python manage.py test tests.test_patterns
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.utils import timezone

from workouts.models import Workout
from fasting.models import FastingSession
from oauth_integration.models import OAuthCredential
from lifetracker.timezone_utils import get_user_timezone, get_user_today


class SourceDeduplicationTests(TestCase):
    """
    PATTERN: Source + Source ID Deduplication

    Every externally-synced model uses `unique_together = ['source', 'source_id']`.
    Sync commands must use `update_or_create()` with BOTH fields as the lookup.
    This ensures re-running a sync never creates duplicates.
    """

    def test_update_or_create_prevents_duplicates(self):
        """Running the same sync twice should update, not duplicate."""
        for _ in range(3):
            Workout.objects.update_or_create(
                source='Whoop',
                source_id='workout_abc123',
                defaults={
                    'start': timezone.now() - timedelta(hours=1),
                    'end': timezone.now(),
                    'sport_id': 0,
                },
            )
        self.assertEqual(Workout.objects.count(), 1)

    def test_same_source_id_different_sources_are_separate(self):
        """Different sources can have the same source_id without conflict."""
        fields = {
            'start': timezone.now() - timedelta(hours=1),
            'end': timezone.now(),
            'sport_id': 0,
        }
        Workout.objects.create(source='Whoop', source_id='123', **fields)
        Workout.objects.create(source='Manual', source_id='123', **fields)
        self.assertEqual(Workout.objects.count(), 2)

    def test_source_names_are_title_cased(self):
        """Source values must be title-cased: 'Whoop' not 'whoop'."""
        Workout.objects.create(
            source='Whoop',
            source_id='test_1',
            start=timezone.now() - timedelta(hours=1),
            end=timezone.now(),
            sport_id=0,
        )
        # Querying with wrong case finds nothing
        self.assertFalse(Workout.objects.filter(source='whoop').exists())
        self.assertTrue(Workout.objects.filter(source='Whoop').exists())

    def test_update_or_create_updates_existing_values(self):
        """Re-syncing with new data should update the existing record."""
        Workout.objects.create(
            source='Whoop',
            source_id='w_456',
            start=timezone.now() - timedelta(hours=1),
            end=timezone.now(),
            sport_id=0,
            calories_burned=200,
        )
        Workout.objects.update_or_create(
            source='Whoop',
            source_id='w_456',
            defaults={'calories_burned': 350},
        )
        workout = Workout.objects.get(source='Whoop', source_id='w_456')
        self.assertEqual(workout.calories_burned, 350)
        self.assertEqual(Workout.objects.count(), 1)

    def test_pattern_works_across_models(self):
        """The source/source_id pattern is consistent across all synced models."""
        now = timezone.now()
        Workout.objects.create(source='Whoop', source_id='1', start=now, end=now, sport_id=0)
        FastingSession.objects.create(source='Zero', source_id='1', fast_end_date=now, duration=16)

        # Same source_id, different models — no conflict
        self.assertEqual(Workout.objects.count(), 1)
        self.assertEqual(FastingSession.objects.count(), 1)


class TimezoneHandlingTests(TestCase):
    """
    PATTERN: Timezone from Browser Cookie

    The user's timezone is read from `request.COOKIES['user_timezone']`.
    All datetimes are stored in UTC. Views convert to user timezone for display.
    Use `get_user_timezone(request)` and `get_user_today(request)` from lifetracker.timezone_utils.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_timezone_from_cookie(self):
        """get_user_timezone reads from the cookie."""
        request = self.factory.get('/')
        request.COOKIES['user_timezone'] = 'America/Los_Angeles'
        tz = get_user_timezone(request)
        self.assertEqual(str(tz), 'America/Los_Angeles')

    def test_timezone_defaults_to_utc(self):
        """Missing cookie falls back to UTC."""
        request = self.factory.get('/')
        request.COOKIES = {}
        tz = get_user_timezone(request)
        self.assertEqual(str(tz), 'UTC')

    def test_invalid_timezone_falls_back_to_utc(self):
        """Invalid timezone string falls back to UTC."""
        request = self.factory.get('/')
        request.COOKIES['user_timezone'] = 'Not/A/Timezone'
        tz = get_user_timezone(request)
        self.assertEqual(str(tz), 'UTC')

    def test_get_user_today_returns_correct_date_for_timezone(self):
        """
        When it's 11 PM in LA (which is 7 AM next day UTC),
        get_user_today should return the LA date, not the UTC date.
        """
        request = self.factory.get('/')
        request.COOKIES['user_timezone'] = 'America/Los_Angeles'

        # Mock: 7 AM UTC on Jan 16 = 11 PM PST on Jan 15
        mock_now = datetime(2025, 1, 16, 7, 0, 0, tzinfo=dt_timezone.utc)
        with patch('django.utils.timezone.now', return_value=mock_now):
            today, today_start, today_end = get_user_today(request)

        # Should be Jan 15 in LA, not Jan 16
        self.assertEqual(today.month, 1)
        self.assertEqual(today.day, 15)

    def test_day_boundaries_are_timezone_aware(self):
        """get_user_today returns timezone-aware start/end datetimes."""
        request = self.factory.get('/')
        request.COOKIES['user_timezone'] = 'US/Eastern'

        today, today_start, today_end = get_user_today(request)

        self.assertIsNotNone(today_start.tzinfo)
        self.assertIsNotNone(today_end.tzinfo)
        self.assertEqual(today_start.hour, 0)
        self.assertEqual(today_start.minute, 0)

    def test_iso_8601_parsing_pattern(self):
        """Frontend sends Z-suffix timestamps. Parse with fromisoformat after replacing Z."""
        frontend_value = '2025-03-15T14:30:00Z'
        parsed = datetime.fromisoformat(frontend_value.replace('Z', '+00:00'))
        self.assertEqual(parsed.year, 2025)
        self.assertEqual(parsed.month, 3)
        self.assertEqual(parsed.hour, 14)
        self.assertIsNotNone(parsed.tzinfo)


class OAuthTokenPersistenceTests(TestCase):
    """
    PATTERN: OAuth Token Persistence

    After refreshing OAuth tokens, call credential.update_tokens() to persist
    them to the database. Use oauth_integration.models.OAuthCredential for all
    OAuth credential storage.
    """

    def test_update_tokens_persists_to_database(self):
        """update_tokens() saves immediately — no separate .save() needed."""
        cred = OAuthCredential.objects.create(
            provider='test_provider',
            client_id='test_id',
            client_secret='test_secret',
            redirect_uri='http://localhost/callback',
            access_token='old_token',
            refresh_token='old_refresh',
        )
        cred.update_tokens(
            access_token='new_token',
            refresh_token='new_refresh',
            expires_in=3600,
        )

        # Reload from database — tokens should be persisted
        cred.refresh_from_db()
        self.assertEqual(cred.access_token, 'new_token')
        self.assertEqual(cred.refresh_token, 'new_refresh')
        self.assertIsNotNone(cred.token_expires_at)

    def test_token_expiration_check(self):
        """is_token_expired() returns True when token has expired."""
        cred = OAuthCredential.objects.create(
            provider='test_expired',
            client_id='id',
            client_secret='secret',
            redirect_uri='http://localhost/callback',
            access_token='token',
            token_expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(cred.is_token_expired())

    def test_token_not_expired(self):
        """is_token_expired() returns False when token is still valid."""
        cred = OAuthCredential.objects.create(
            provider='test_valid',
            client_id='id',
            client_secret='secret',
            redirect_uri='http://localhost/callback',
            access_token='token',
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertFalse(cred.is_token_expired())

    def test_missing_expiration_counts_as_expired(self):
        """No token_expires_at means the token is considered expired."""
        cred = OAuthCredential.objects.create(
            provider='test_no_expiry',
            client_id='id',
            client_secret='secret',
            redirect_uri='http://localhost/callback',
            access_token='token',
        )
        self.assertTrue(cred.is_token_expired())


class AjaxResponseFormatTests(TestCase):
    """
    PATTERN: AJAX Response Format

    All AJAX endpoints return {'success': bool, ...} with appropriate status codes.
    Errors include an 'error' key with a message string.
    """

    def test_success_response_format(self):
        """Success responses include 'success': True."""
        from django.http import JsonResponse
        import json

        response = JsonResponse({'success': True, 'data': {'id': 1}})
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.assertEqual(response.status_code, 200)

    def test_error_response_format(self):
        """Error responses include 'success': False and 'error' message."""
        from django.http import JsonResponse
        import json

        response = JsonResponse(
            {'success': False, 'error': 'Not found'},
            status=404,
        )
        body = json.loads(response.content)
        self.assertFalse(body['success'])
        self.assertIn('error', body)
        self.assertEqual(response.status_code, 404)
