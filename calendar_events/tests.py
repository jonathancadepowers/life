from django.test import TestCase
from django.db import IntegrityError
from datetime import datetime, timezone as dt_timezone

from calendar_events.models import CalendarEvent
from calendar_events.views import import_calendar_events, _parse_event_times, _upsert_event


class CalendarEventModelTests(TestCase):
    """Tests for the CalendarEvent model."""

    def test_create_event_with_required_fields(self):
        """Create event with required fields: outlook_id, subject, start, end."""
        start = datetime(2026, 2, 7, 10, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 2, 7, 11, 0, tzinfo=dt_timezone.utc)
        event = CalendarEvent.objects.create(
            outlook_id='evt-001',
            subject='Team Meeting',
            start=start,
            end=end,
        )
        self.assertEqual(event.outlook_id, 'evt-001')
        self.assertEqual(event.subject, 'Team Meeting')
        self.assertEqual(event.start, start)
        self.assertEqual(event.end, end)

    def test_outlook_id_unique_constraint(self):
        """outlook_id must be unique across events."""
        start = datetime(2026, 2, 7, 10, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 2, 7, 11, 0, tzinfo=dt_timezone.utc)
        CalendarEvent.objects.create(
            outlook_id='evt-dup',
            subject='First',
            start=start,
            end=end,
        )
        with self.assertRaises(IntegrityError):
            CalendarEvent.objects.create(
                outlook_id='evt-dup',
                subject='Second',
                start=start,
                end=end,
            )

    def test_str_shows_subject_and_formatted_date(self):
        """__str__ returns subject and formatted start date."""
        start = datetime(2026, 2, 7, 10, 30, tzinfo=dt_timezone.utc)
        end = datetime(2026, 2, 7, 11, 30, tzinfo=dt_timezone.utc)
        event = CalendarEvent.objects.create(
            outlook_id='evt-str',
            subject='Standup',
            start=start,
            end=end,
        )
        self.assertEqual(str(event), 'Standup (2026-02-07 10:30)')

    def test_override_fields_can_be_set(self):
        """override_start and override_end can be set on an event."""
        start = datetime(2026, 2, 7, 10, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 2, 7, 11, 0, tzinfo=dt_timezone.utc)
        override_start = datetime(2026, 2, 7, 10, 30, tzinfo=dt_timezone.utc)
        override_end = datetime(2026, 2, 7, 11, 30, tzinfo=dt_timezone.utc)
        event = CalendarEvent.objects.create(
            outlook_id='evt-override',
            subject='Flexible Meeting',
            start=start,
            end=end,
            override_start=override_start,
            override_end=override_end,
        )
        self.assertEqual(event.override_start, override_start)
        self.assertEqual(event.override_end, override_end)

    def test_is_hidden_defaults_to_false(self):
        """is_hidden defaults to False and can be set to True."""
        start = datetime(2026, 2, 7, 10, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 2, 7, 11, 0, tzinfo=dt_timezone.utc)
        event = CalendarEvent.objects.create(
            outlook_id='evt-hidden',
            subject='Secret Meeting',
            start=start,
            end=end,
        )
        self.assertFalse(event.is_hidden)

        event.is_hidden = True
        event.save()
        event.refresh_from_db()
        self.assertTrue(event.is_hidden)

    def test_is_active_defaults_to_true(self):
        """is_active defaults to True."""
        start = datetime(2026, 2, 7, 10, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 2, 7, 11, 0, tzinfo=dt_timezone.utc)
        event = CalendarEvent.objects.create(
            outlook_id='evt-active',
            subject='Active Meeting',
            start=start,
            end=end,
        )
        self.assertTrue(event.is_active)


class ParseEventTimesTests(TestCase):
    """Tests for _parse_event_times helper."""

    def test_valid_iso_strings_returns_tuple(self):
        """Valid ISO datetime strings return (start_dt, end_dt) tuple."""
        event = {
            'start': '2026-02-07T10:00:00',
            'end': '2026-02-07T11:00:00',
        }
        result = _parse_event_times(event)
        self.assertIsNotNone(result)
        start_dt, end_dt = result
        self.assertEqual(start_dt, datetime(2026, 2, 7, 10, 0, tzinfo=dt_timezone.utc))
        self.assertEqual(end_dt, datetime(2026, 2, 7, 11, 0, tzinfo=dt_timezone.utc))

    def test_missing_start_returns_none(self):
        """Missing start returns None."""
        event = {'end': '2026-02-07T11:00:00'}
        result = _parse_event_times(event)
        self.assertIsNone(result)

    def test_missing_end_returns_none(self):
        """Missing end returns None."""
        event = {'start': '2026-02-07T10:00:00'}
        result = _parse_event_times(event)
        self.assertIsNone(result)


class ImportCalendarEventsTests(TestCase):
    """Tests for import_calendar_events function."""

    def test_creates_events_from_valid_data(self):
        """Creates events from valid input data."""
        events_data = {'body': [
            {'id': 'evt1', 'subject': 'Meeting', 'start': '2026-02-07T10:00:00', 'end': '2026-02-07T11:00:00'},
            {'id': 'evt2', 'subject': 'Lunch', 'start': '2026-02-07T12:00:00', 'end': '2026-02-07T13:00:00'},
        ]}
        created, updated, canceled = import_calendar_events(events_data)
        self.assertEqual(created, 2)
        self.assertEqual(updated, 0)
        self.assertEqual(CalendarEvent.objects.count(), 2)

    def test_updates_existing_events_same_outlook_id(self):
        """Importing same outlook_id with different subject updates the event."""
        start = datetime(2026, 2, 7, 10, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 2, 7, 11, 0, tzinfo=dt_timezone.utc)
        CalendarEvent.objects.create(
            outlook_id='evt-update',
            subject='Old Subject',
            start=start,
            end=end,
        )
        events_data = {'body': [
            {'id': 'evt-update', 'subject': 'New Subject', 'start': '2026-02-07T10:00:00', 'end': '2026-02-07T11:00:00'},
        ]}
        created, updated, canceled = import_calendar_events(events_data)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        event = CalendarEvent.objects.get(outlook_id='evt-update')
        self.assertEqual(event.subject, 'New Subject')

    def test_updates_by_subject_start_match_when_outlook_id_changes(self):
        """When outlook_id changes but subject+start match, updates existing event."""
        start = datetime(2026, 2, 7, 14, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 2, 7, 15, 0, tzinfo=dt_timezone.utc)
        CalendarEvent.objects.create(
            outlook_id='old-id',
            subject='Recurring Meeting',
            start=start,
            end=end,
        )
        events_data = {'body': [
            {'id': 'new-id', 'subject': 'Recurring Meeting', 'start': '2026-02-07T14:00:00', 'end': '2026-02-07T15:00:00'},
        ]}
        created, updated, canceled = import_calendar_events(events_data)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        # The old event should now have the new outlook_id
        self.assertFalse(CalendarEvent.objects.filter(outlook_id='old-id').exists())
        self.assertTrue(CalendarEvent.objects.filter(outlook_id='new-id').exists())
        # Total count should still be 1
        self.assertEqual(CalendarEvent.objects.count(), 1)

    def test_cancels_missing_events_in_date_range(self):
        """Events in the import date range not included in import are marked inactive."""
        start = datetime(2026, 2, 7, 9, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 2, 7, 10, 0, tzinfo=dt_timezone.utc)
        CalendarEvent.objects.create(
            outlook_id='evt-to-cancel',
            subject='Will Be Canceled',
            start=start,
            end=end,
            is_active=True,
        )
        # Import events for the same date but without the existing event
        events_data = {'body': [
            {'id': 'evt-keep', 'subject': 'Kept', 'start': '2026-02-07T12:00:00', 'end': '2026-02-07T13:00:00'},
        ]}
        created, updated, canceled = import_calendar_events(events_data)
        self.assertEqual(created, 1)
        self.assertEqual(canceled, 1)
        canceled_event = CalendarEvent.objects.get(outlook_id='evt-to-cancel')
        self.assertFalse(canceled_event.is_active)

    def test_empty_body_returns_zeros(self):
        """Empty body list returns (0, 0, 0)."""
        events_data = {'body': []}
        created, updated, canceled = import_calendar_events(events_data)
        self.assertEqual((created, updated, canceled), (0, 0, 0))

    def test_missing_body_key_returns_zeros(self):
        """Missing body key returns (0, 0, 0)."""
        events_data = {}
        created, updated, canceled = import_calendar_events(events_data)
        self.assertEqual((created, updated, canceled), (0, 0, 0))

    def test_events_without_id_are_skipped(self):
        """Events missing the 'id' field are skipped."""
        events_data = {'body': [
            {'subject': 'No ID', 'start': '2026-02-07T10:00:00', 'end': '2026-02-07T11:00:00'},
            {'id': 'evt-has-id', 'subject': 'Has ID', 'start': '2026-02-07T12:00:00', 'end': '2026-02-07T13:00:00'},
        ]}
        created, updated, canceled = import_calendar_events(events_data)
        self.assertEqual(created, 1)
        self.assertEqual(CalendarEvent.objects.count(), 1)
        self.assertEqual(CalendarEvent.objects.first().outlook_id, 'evt-has-id')


class UpsertEventTests(TestCase):
    """Tests for _upsert_event helper."""

    def test_creates_new_event_when_no_match(self):
        """Creates a new event when no existing event matches."""
        start_dt = datetime(2026, 2, 7, 10, 0, tzinfo=dt_timezone.utc)
        end_dt = datetime(2026, 2, 7, 11, 0, tzinfo=dt_timezone.utc)
        defaults = {
            'subject': 'Brand New',
            'start': start_dt,
            'end': end_dt,
            'is_all_day': False,
            'location': '',
            'organizer': '',
            'body_preview': '',
            'is_active': True,
            'override_start': None,
            'override_end': None,
            'is_hidden': False,
        }
        db_id, action = _upsert_event('new-outlook-id', 'Brand New', start_dt, defaults)
        self.assertEqual(action, 'created')
        self.assertTrue(CalendarEvent.objects.filter(id=db_id).exists())

    def test_updates_existing_by_outlook_id(self):
        """Updates existing event found by outlook_id."""
        start_dt = datetime(2026, 2, 7, 10, 0, tzinfo=dt_timezone.utc)
        end_dt = datetime(2026, 2, 7, 11, 0, tzinfo=dt_timezone.utc)
        existing = CalendarEvent.objects.create(
            outlook_id='existing-id',
            subject='Old Name',
            start=start_dt,
            end=end_dt,
        )
        defaults = {
            'subject': 'Updated Name',
            'start': start_dt,
            'end': end_dt,
            'is_all_day': False,
            'location': 'Room 101',
            'organizer': '',
            'body_preview': '',
            'is_active': True,
            'override_start': None,
            'override_end': None,
            'is_hidden': False,
        }
        db_id, action = _upsert_event('existing-id', 'Updated Name', start_dt, defaults)
        self.assertEqual(action, 'updated')
        self.assertEqual(db_id, existing.id)
        existing.refresh_from_db()
        self.assertEqual(existing.subject, 'Updated Name')
        self.assertEqual(existing.location, 'Room 101')

    def test_updates_existing_by_subject_start_match(self):
        """Updates existing event found by subject+start when outlook_id doesn't match."""
        start_dt = datetime(2026, 2, 7, 14, 0, tzinfo=dt_timezone.utc)
        end_dt = datetime(2026, 2, 7, 15, 0, tzinfo=dt_timezone.utc)
        existing = CalendarEvent.objects.create(
            outlook_id='old-outlook-id',
            subject='Weekly Sync',
            start=start_dt,
            end=end_dt,
        )
        defaults = {
            'subject': 'Weekly Sync',
            'start': start_dt,
            'end': end_dt,
            'is_all_day': False,
            'location': '',
            'organizer': '',
            'body_preview': '',
            'is_active': True,
            'override_start': None,
            'override_end': None,
            'is_hidden': False,
        }
        db_id, action = _upsert_event('new-outlook-id', 'Weekly Sync', start_dt, defaults)
        self.assertEqual(action, 'updated')
        self.assertEqual(db_id, existing.id)
        existing.refresh_from_db()
        self.assertEqual(existing.outlook_id, 'new-outlook-id')
