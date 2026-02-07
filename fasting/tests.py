from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import datetime
import json

from fasting.models import FastingSession
from projects.models import Project
from targets.models import DailyAgenda


class FastingAPITestCase(TestCase):
    """Tests for Fasting API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

    def test_log_fast_today_12_hours(self):
        """Test logging a 12-hour fast"""
        data = {
            'hours': '12',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertIn('12-hour fast logged successfully', result['message'])
        self.assertEqual(result['duration'], 12.0)

        # Verify fast was created
        fast = FastingSession.objects.get(id=result['fast_id'])
        self.assertEqual(fast.duration, 12)
        self.assertEqual(fast.source, 'Manual')

    def test_log_fast_today_16_hours(self):
        """Test logging a 16-hour fast"""
        data = {
            'hours': '16',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertEqual(result['duration'], 16.0)

    def test_log_fast_today_18_hours(self):
        """Test logging an 18-hour fast"""
        data = {
            'hours': '18',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertEqual(result['duration'], 18.0)

    def test_log_fast_past_date(self):
        """Test logging a fast for a past date"""
        import pytz

        data = {
            'hours': '16',
            'date': '2025-10-27'
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])

        # Verify the end date is at noon in America/Chicago timezone
        # (the default when no timezone cookie is set)
        fast = FastingSession.objects.get(id=result['fast_id'])
        self.assertEqual(fast.fast_end_date.date(), datetime(2025, 10, 27).date())

        # Convert to America/Chicago timezone (the default used in views)
        chicago_tz = pytz.timezone('America/Chicago')
        chicago_time = fast.fast_end_date.astimezone(chicago_tz)
        self.assertEqual(chicago_time.hour, 12)

    def test_log_fast_invalid_hours(self):
        """Test logging a fast with invalid duration"""
        data = {
            'hours': '20',  # Invalid duration
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('must be 12, 16, or 18', result['message'])

    def test_log_fast_missing_hours(self):
        """Test logging a fast without duration"""
        data = {
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('required', result['message'])

    def test_log_fast_invalid_date_format(self):
        """Test logging a fast with invalid date format"""
        data = {
            'hours': '12',
            'date': 'invalid-date'  # Invalid date format
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('date format', result['message'])

    def test_log_fast_non_numeric_hours(self):
        """Test logging a fast with non-numeric hours"""
        data = {
            'hours': 'abc',
            'date': '2025-10-28'
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result['success'])

    def test_activity_logger_page_loads(self):
        """Test that the activity logger page loads successfully"""
        # Create a test project to avoid empty page issues
        Project.objects.create(
            project_id=123,
            display_string='Test Project'
        )

        response = self.client.get(reverse('fasting:activity_logger'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activity Logger')
        self.assertContains(response, 'Fasting')

    def test_activity_logger_with_agenda(self):
        """Test activity logger page with existing agenda"""
        # Create test data
        project = Project.objects.create(
            project_id=123,
            display_string='Test Project'
        )
        today = timezone.now().date()
        DailyAgenda.objects.create(
            date=today,
            project_1=project
        )

        response = self.client.get(reverse('fasting:activity_logger'))
        self.assertEqual(response.status_code, 200)

    def test_activity_logger_does_not_pass_agenda_in_context(self):
        """
        Test that activity_logger view does NOT pass agenda in context.

        This ensures we maintain timezone-agnostic behavior where JavaScript
        determines the user's local date and fetches the agenda via AJAX,
        rather than the server determining "today" in a hardcoded timezone.

        Regression test for timezone bug where server-side date lookup
        failed for users in different timezones.
        """
        # Create test data
        project = Project.objects.create(
            project_id=123,
            display_string='Test Project'
        )
        today = timezone.now().date()
        DailyAgenda.objects.create(
            date=today,
            project_1=project
        )

        # Get the response
        response = self.client.get(reverse('fasting:activity_logger'))
        self.assertEqual(response.status_code, 200)

        # CRITICAL: Verify that agenda is None in context
        # This forces JavaScript to fetch agenda based on user's browser timezone
        self.assertIsNone(response.context.get('agenda'),
            "activity_logger view should NOT pass agenda in context. "
            "JavaScript should fetch it based on user's local timezone to avoid timezone bugs."
        )


class FastingModelTestCase(TestCase):
    """Tests for Fasting model"""

    def test_create_fasting_session(self):
        """Test creating a fasting session"""
        now = timezone.now()
        session = FastingSession.objects.create(
            source='Manual',
            source_id='test-123',
            duration=16,
            fast_end_date=now
        )

        self.assertEqual(session.source, 'Manual')
        self.assertEqual(session.duration, 16)
        self.assertEqual(session.fast_end_date, now)

    def test_unique_source_constraint(self):
        """Test that duplicate source entries are prevented"""
        now = timezone.now()
        FastingSession.objects.create(
            source='Manual',
            source_id='test-123',
            duration=16,
            fast_end_date=now
        )

        # Should raise error for duplicate source + source_id
        with self.assertRaises(Exception):
            FastingSession.objects.create(
                source='Manual',
                source_id='test-123',
                duration=18,
                fast_end_date=now
            )
