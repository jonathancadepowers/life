from datetime import datetime, timezone, timedelta

from .models import CalendarEvent


def _parse_event_times(event):
    """Parse start and end datetime strings from an event dict.

    Returns (start_dt, end_dt) as timezone-aware datetimes, or None if parsing fails.
    """
    start_str = event.get("start", "")
    end_str = event.get("end", "")

    if not start_str or not end_str:
        return None

    start_dt = datetime.fromisoformat(start_str[:19]).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end_str[:19]).replace(tzinfo=timezone.utc)
    return start_dt, end_dt


def _build_event_defaults(event, start_dt, end_dt, source):
    """Build the defaults dict for creating/updating a CalendarEvent."""
    defaults = {
        "subject": event.get("subject", "")[:500],
        "start": start_dt,
        "end": end_dt,
        "is_all_day": event.get("isAllDay", False),
        "location": event.get("location", "")[:500],
        "organizer": event.get("organizer", "")[:255],
        "body_preview": event.get("bodyPreview", ""),
        "is_active": True,
        "override_start": None,
        "override_end": None,
        "is_hidden": False,
    }
    if source:
        defaults["source"] = source
    return defaults


def _upsert_event(outlook_id, subject, start_dt, defaults):
    """Find an existing event by outlook_id or (subject, start), then update or create.

    Returns (db_id, action) where action is 'created' or 'updated'.
    """
    existing = CalendarEvent.objects.filter(outlook_id=outlook_id).first()
    if existing:
        for key, value in defaults.items():
            setattr(existing, key, value)
        existing.save()
        return existing.id, "updated"

    existing = CalendarEvent.objects.filter(subject=subject, start=start_dt).first()
    if existing:
        for key, value in defaults.items():
            setattr(existing, key, value)
        existing.outlook_id = outlook_id
        existing.save()
        return existing.id, "updated"

    obj = CalendarEvent.objects.create(outlook_id=outlook_id, **defaults)
    return obj.id, "created"


def _cancel_missing_events(min_date, max_date, processed_ids):
    """Mark active events in the date range as canceled if they were not processed."""
    if not min_date or not max_date:
        return 0

    range_start = datetime.combine(min_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    range_end = datetime.combine(max_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)

    return (
        CalendarEvent.objects.filter(start__gte=range_start, start__lt=range_end, is_active=True)
        .exclude(id__in=processed_ids)
        .update(is_active=False)
    )


def import_calendar_events(events_data, source=""):
    """
    Import calendar events from a list of event dictionaries.
    Returns tuple of (created_count, updated_count, canceled_count).

    Key behaviors:
    1. Each event has a unique ID (database primary key) - even recurring instances
    2. If an event's time changes, we update the existing record (preserving ID for notes)
    3. If an event is removed from the JSON (canceled), we mark is_active=False but keep the record

    Args:
        events_data: Dict with 'body' key containing list of events
        source: Source identifier to store with each event (e.g., "Oxy Calendar Import")
    """
    created_count = 0
    updated_count = 0

    events = events_data.get("body", [])
    if not events:
        return created_count, updated_count, 0

    processed_ids = set()
    min_date = None
    max_date = None

    for event in events:
        outlook_id = event.get("id")
        if not outlook_id:
            continue

        parsed = _parse_event_times(event)
        if not parsed:
            continue
        start_dt, end_dt = parsed

        # Track the date range of events in this import
        event_date = start_dt.date()
        if min_date is None or event_date < min_date:
            min_date = event_date
        if max_date is None or event_date > max_date:
            max_date = event_date

        subject = event.get("subject", "")[:500]
        defaults = _build_event_defaults(event, start_dt, end_dt, source)

        db_id, action = _upsert_event(outlook_id, subject, start_dt, defaults)
        processed_ids.add(db_id)
        if action == "created":
            created_count += 1
        else:
            updated_count += 1

    canceled_count = _cancel_missing_events(min_date, max_date, processed_ids)

    return created_count, updated_count, canceled_count
