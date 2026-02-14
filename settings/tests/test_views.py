import json

from django.test import TestCase
from django.urls import reverse

from settings.models import LifeTrackerColumn


class LifeTrackerSettingsViewTests(TestCase):
    """Tests for the life_tracker_settings GET view."""

    def test_get_returns_200_with_columns_in_context(self):
        """GET /settings/ should return 200 and include 'columns' in context."""
        response = self.client.get(reverse('life_tracker_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('columns', response.context)


class ToggleAbandonDayViewTests(TestCase):
    """Tests for the toggle_abandon_day view."""

    def setUp(self):
        self.column = LifeTrackerColumn.objects.create(
            column_name='test_toggle',
            display_name='Test Toggle',
            tooltip_text='Test tooltip',
            sql_query='SELECT 0',
            allow_abandon=True,
        )

    def test_toggle_on(self):
        """First POST should set is_abandoned to True."""
        url = reverse('toggle_abandon_day', args=[self.column.column_name])
        response = self.client.post(
            url,
            data=json.dumps({'date': '2026-01-15'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_abandoned'])

    def test_toggle_off(self):
        """Second POST for the same date should toggle is_abandoned to False."""
        url = reverse('toggle_abandon_day', args=[self.column.column_name])
        # First toggle: on
        self.client.post(
            url,
            data=json.dumps({'date': '2026-01-15'}),
            content_type='application/json',
        )
        # Second toggle: off
        response = self.client.post(
            url,
            data=json.dumps({'date': '2026-01-15'}),
            content_type='application/json',
        )
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['is_abandoned'])

    def test_missing_date_returns_400(self):
        """POST without a date should return 400."""
        url = reverse('toggle_abandon_day', args=[self.column.column_name])
        response = self.client.post(
            url,
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])

    def test_nonexistent_column_returns_404(self):
        """POST to a non-existent column_name should return 404."""
        url = reverse('toggle_abandon_day', args=['nonexistent'])
        response = self.client.post(
            url,
            data=json.dumps({'date': '2026-01-15'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)


class AddHabitViewTests(TestCase):
    """Tests for the add_habit view."""

    def test_missing_required_fields_returns_redirect_with_error(self):
        """POST with missing required fields should redirect with an error message."""
        url = reverse('add_habit')
        response = self.client.post(url, data={
            'column_name': '',
            'display_name': '',
            'tooltip_text': '',
            'sql_query': '',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        messages_list = list(response.context['messages'])
        self.assertTrue(any('required fields' in str(m).lower() for m in messages_list))

    def test_duplicate_column_name_returns_redirect_with_error(self):
        """POST with an existing column_name should redirect with an error message."""
        LifeTrackerColumn.objects.create(
            column_name='test_dup',
            display_name='Test Dup',
            tooltip_text='Duplicate habit',
            sql_query='SELECT 1',
        )
        url = reverse('add_habit')
        response = self.client.post(url, data={
            'column_name': 'test_dup',
            'display_name': 'Test Dup Again',
            'tooltip_text': 'Another test dup',
            'sql_query': 'SELECT 1',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        messages_list = list(response.context['messages'])
        self.assertTrue(any('already exists' in str(m).lower() for m in messages_list))


class DeleteInspirationViewTests(TestCase):
    """Tests for the delete_inspiration view."""

    def test_nonexistent_id_returns_404(self):
        """POST to delete a non-existent Inspiration should return 404."""
        url = reverse('delete_inspiration', args=[99999])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class DeleteWritingImageViewTests(TestCase):
    """Tests for the delete_writing_image view."""

    def test_nonexistent_id_returns_404(self):
        """POST to delete a non-existent WritingPageImage should return 404."""
        url = reverse('delete_writing_image', args=[99999])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
