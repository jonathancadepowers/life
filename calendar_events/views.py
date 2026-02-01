from datetime import datetime, timezone

from .models import CalendarEvent


def import_calendar_events(events_data, source=''):
    """
    Import calendar events from a list of event dictionaries.
    Returns tuple of (created_count, updated_count).

    Args:
        events_data: Dict with 'body' key containing list of events
        source: Source identifier to store with each event (e.g., "Oxy Calendar Import")
    """
    created_count = 0
    updated_count = 0

    events = events_data.get('body', [])

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
        }
        if source:
            defaults['source'] = source

        # For recurring meetings, Outlook assigns different IDs to each occurrence.
        # Check if an event with the same subject and start time already exists.
        existing_by_time = CalendarEvent.objects.filter(
            subject=subject,
            start=start_dt
        ).first()

        if existing_by_time:
            # Update the existing event (found by subject + start time)
            for key, value in defaults.items():
                setattr(existing_by_time, key, value)
            existing_by_time.save()
            updated_count += 1
        else:
            # No existing event at this time - use update_or_create by outlook_id
            obj, created = CalendarEvent.objects.update_or_create(
                outlook_id=outlook_id,
                defaults=defaults
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

    return created_count, updated_count
