from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta, datetime, time
from .models import FastingSession
import uuid


def activity_logger(request):
    """Render the Activity Logger page."""
    return render(request, 'fasting/activity_logger.html')


@require_http_methods(["POST"])
def log_fast(request):
    """
    AJAX endpoint to log a new fast.

    Expects POST data:
        - hours: integer (12, 16, or 18)
        - day: string ('today' or 'yesterday')

    Returns JSON:
        - success: boolean
        - message: string
        - fast_id: integer (if successful)
    """
    try:
        # Get the fast duration and day from POST data
        hours = request.POST.get('hours')
        day = request.POST.get('day', 'today')

        if not hours:
            return JsonResponse({
                'success': False,
                'message': 'Fast duration is required'
            }, status=400)

        try:
            hours = int(hours)
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid fast duration'
            }, status=400)

        if hours not in [12, 16, 18]:
            return JsonResponse({
                'success': False,
                'message': 'Fast duration must be 12, 16, or 18 hours'
            }, status=400)

        if day not in ['today', 'yesterday']:
            return JsonResponse({
                'success': False,
                'message': 'Day must be "today" or "yesterday"'
            }, status=400)

        # Calculate end and start times based on day
        if day == 'today':
            # End time is now, start time is X hours ago
            end_time = timezone.now()
            start_time = end_time - timedelta(hours=hours)
        else:  # yesterday
            # End time is noon yesterday, start time is noon yesterday - X hours
            now = timezone.now()
            yesterday = now - timedelta(days=1)
            # Create noon yesterday (12:00 PM)
            end_time = timezone.make_aware(
                datetime.combine(yesterday.date(), time(12, 0))
            )
            start_time = end_time - timedelta(hours=hours)

        # Generate a unique source_id for manual entries
        source_id = str(uuid.uuid4())

        fast = FastingSession.objects.create(
            source='Manual',
            source_id=source_id,
            start=start_time,
            end=end_time,
        )

        day_label = 'Today' if day == 'today' else 'Yesterday'
        return JsonResponse({
            'success': True,
            'message': f'{day_label}: {hours}-hour fast logged successfully!',
            'fast_id': fast.id,
            'start': start_time.strftime('%Y-%m-%d %H:%M'),
            'end': end_time.strftime('%Y-%m-%d %H:%M')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error logging fast: {str(e)}'
        }, status=500)
