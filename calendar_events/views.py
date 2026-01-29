import json
import hashlib
import hmac
from datetime import datetime, timezone

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

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

        # Use update_or_create for idempotent import
        defaults = {
            'subject': event.get('subject', '')[:500],
            'start': start_dt,
            'end': end_dt,
            'is_all_day': event.get('isAllDay', False),
            'location': event.get('location', '')[:500],
            'organizer': event.get('organizer', '')[:255],
            'body_preview': event.get('bodyPreview', ''),
        }
        if source:
            defaults['source'] = source

        obj, created = CalendarEvent.objects.update_or_create(
            outlook_id=outlook_id,
            defaults=defaults
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return created_count, updated_count


def verify_mailgun_signature(token, timestamp, signature, api_key):
    """Verify that the request came from Mailgun."""
    hmac_digest = hmac.new(
        key=api_key.encode('utf-8'),
        msg=f'{timestamp}{token}'.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(str(signature), str(hmac_digest))


@csrf_exempt
@require_POST
def mailgun_webhook(request):
    """
    Webhook endpoint for receiving calendar exports via email (Mailgun).

    Mailgun sends parsed emails as multipart/form-data with:
    - sender, recipient, subject, body-plain, etc.
    - attachments as files
    - signature verification fields: token, timestamp, signature

    Forward your calendar export email to: calendar@mail.yourdomain.com
    """
    # Get Mailgun API key for signature verification
    mailgun_api_key = getattr(settings, 'MAILGUN_API_KEY', None)

    # Verify Mailgun signature (optional but recommended)
    if mailgun_api_key:
        token = request.POST.get('token', '')
        timestamp = request.POST.get('timestamp', '')
        signature = request.POST.get('signature', '')

        if not verify_mailgun_signature(token, timestamp, signature, mailgun_api_key):
            return HttpResponse('Invalid signature', status=403)

    # Log some info for debugging
    sender = request.POST.get('sender', '')
    subject = request.POST.get('subject', '')

    # Look for JSON attachments
    json_data = None
    attachment_count = int(request.POST.get('attachment-count', 0))

    # Check numbered attachments (attachment-1, attachment-2, etc.)
    for i in range(1, attachment_count + 1):
        attachment = request.FILES.get(f'attachment-{i}')
        if attachment and attachment.name.endswith('.json'):
            try:
                content = attachment.read().decode('utf-8')
                json_data = json.loads(content)
                break
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

    # Also check generic 'attachment' key
    if not json_data:
        attachment = request.FILES.get('attachment')
        if attachment and attachment.name.endswith('.json'):
            try:
                content = attachment.read().decode('utf-8')
                json_data = json.loads(content)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

    if not json_data:
        return HttpResponse(
            f'No valid JSON attachment found. Sender: {sender}, Subject: {subject}',
            status=400
        )

    # Import the calendar events
    try:
        created_count, updated_count = import_calendar_events(json_data)
        return HttpResponse(
            f'Success! {created_count} events created, {updated_count} events updated. '
            f'From: {sender}, Subject: {subject}',
            status=200
        )
    except Exception as e:
        return HttpResponse(f'Import error: {str(e)}', status=500)


@csrf_exempt
@require_POST
def webhook_import(request):
    """
    Webhook endpoint for importing calendar events via API.

    Expects:
    - Header: X-API-Key with the correct API key
    - Body: JSON with calendar events in Outlook export format

    Example curl:
    curl -X POST https://yourapp.herokuapp.com/api/calendar/import/ \
         -H "Content-Type: application/json" \
         -H "X-API-Key: your-api-key" \
         -d @calendar-export.json
    """
    # Verify API key
    api_key = request.headers.get('X-API-Key', '')
    expected_key = getattr(settings, 'CALENDAR_IMPORT_API_KEY', None)

    if not expected_key:
        return JsonResponse({
            'success': False,
            'error': 'API key not configured on server'
        }, status=500)

    if api_key != expected_key:
        return JsonResponse({
            'success': False,
            'error': 'Invalid or missing API key'
        }, status=401)

    # Parse JSON body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({
            'success': False,
            'error': f'Invalid JSON: {str(e)}'
        }, status=400)

    # Import events
    try:
        created_count, updated_count = import_calendar_events(data)
        return JsonResponse({
            'success': True,
            'created': created_count,
            'updated': updated_count,
            'message': f'{created_count} events created, {updated_count} events updated'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
