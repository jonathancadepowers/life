from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, datetime, time
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
        """Test logging a 12-hour fast for today"""
        data = {
            'hours': '12',
            'day': 'today'
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
        """Test logging a 16-hour fast for today"""
        data = {
            'hours': '16',
            'day': 'today'
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
        """Test logging an 18-hour fast for today"""
        data = {
            'hours': '18',
            'day': 'today'
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertEqual(result['duration'], 18.0)

    def test_log_fast_yesterday(self):
        """Test logging a fast for yesterday"""
        data = {
            'hours': '16',
            'day': 'yesterday'
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertIn('Yesterday', result['message'])

        # Verify the end date is yesterday at noon
        fast = FastingSession.objects.get(id=result['fast_id'])
        yesterday = timezone.now() - timedelta(days=1)
        self.assertEqual(fast.fast_end_date.date(), yesterday.date())
        self.assertEqual(fast.fast_end_date.hour, 12)

    def test_log_fast_invalid_hours(self):
        """Test logging a fast with invalid duration"""
        data = {
            'hours': '20',  # Invalid duration
            'day': 'today'
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
            'day': 'today'
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('required', result['message'])

    def test_log_fast_invalid_day(self):
        """Test logging a fast with invalid day"""
        data = {
            'hours': '12',
            'day': 'tomorrow'  # Invalid day
        }

        response = self.client.post(
            reverse('fasting:log_fast'),
            data=data
        )

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('must be "today" or "yesterday"', result['message'])

    def test_log_fast_non_numeric_hours(self):
        """Test logging a fast with non-numeric hours"""
        data = {
            'hours': 'abc',
            'day': 'today'
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
