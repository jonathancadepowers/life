from datetime import datetime, timezone, timedelta

from .models import CalendarEvent


def import_calendar_events(events_data, source=''):
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
    canceled_count = 0

    events = events_data.get('body', [])
    if not events:
        return created_count, updated_count, canceled_count

    # Track date range and processed event IDs
    processed_ids = set()
    min_date = None
    max_date = None

    for event in events:
        outlook_id = event.get('id')
        if not outlook_id:
            continue

        # Parse datetime strings (format: 2026-01-30T15:00:00.0000000)
        # Outlook exports times in UTC
        start_str = event.get('start', '')
        end_str = event.get('end', '')

        # Remove extra precision and parse as UTC
        if start_str:
            start_str = start_str[:19]  # Trim to 2026-01-30T15:00:00
            start_dt = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
        else:
            continue

        if end_str:
            end_str = end_str[:19]
            end_dt = datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc)
        else:
            continue

        # Track the date range of events in this import
        event_date = start_dt.date()
        if min_date is None or event_date < min_date:
            min_date = event_date
        if max_date is None or event_date > max_date:
            max_date = event_date

        subject = event.get('subject', '')[:500]

        # Build the defaults dict
        defaults = {
            'subject': subject,
            'start': start_dt,
            'end': end_dt,
            'is_all_day': event.get('isAllDay', False),
            'location': event.get('location', '')[:500],
            'organizer': event.get('organizer', '')[:255],
            'body_preview': event.get('bodyPreview', ''),
            'is_active': True,  # Re-activate in case it was previously canceled
        }
        if source:
            defaults['source'] = source

        # Primary lookup: by outlook_id
        # This preserves the event's database ID even if the time changes
        existing_by_outlook_id = CalendarEvent.objects.filter(outlook_id=outlook_id).first()

        if existing_by_outlook_id:
            # Update existing event (handles time changes while preserving ID)
            for key, value in defaults.items():
                setattr(existing_by_outlook_id, key, value)
            existing_by_outlook_id.save()
            processed_ids.add(existing_by_outlook_id.id)
            updated_count += 1
        else:
            # New outlook_id - check for duplicate by (subject, start_time)
            # This handles recurring meetings that may have different outlook_ids
            existing_by_time = CalendarEvent.objects.filter(
                subject=subject,
                start=start_dt
            ).first()

            if existing_by_time:
                # Update existing event found by subject+time
                for key, value in defaults.items():
                    setattr(existing_by_time, key, value)
                # Also update the outlook_id to the new one
                existing_by_time.outlook_id = outlook_id
                existing_by_time.save()
                processed_ids.add(existing_by_time.id)
                updated_count += 1
            else:
                # Create new event
                obj = CalendarEvent.objects.create(
                    outlook_id=outlook_id,
                    **defaults
                )
                processed_ids.add(obj.id)
                created_count += 1

    # Mark events as canceled if they're in the date range but weren't in the JSON
    # This handles events that were deleted/canceled from the calendar
    if min_date and max_date:
        # Convert dates to datetime for filtering
        range_start = datetime.combine(min_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        range_end = datetime.combine(max_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)

        # Find active events in the date range that weren't processed
        events_to_cancel = CalendarEvent.objects.filter(
            start__gte=range_start,
            start__lt=range_end,
            is_active=True
        ).exclude(id__in=processed_ids)

        canceled_count = events_to_cancel.update(is_active=False)

    return created_count, updated_count, canceled_count
