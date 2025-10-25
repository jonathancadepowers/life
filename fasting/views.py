from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta, datetime, time
from .models import FastingSession
from django.core.management import call_command
from io import StringIO
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

        # Calculate fast_end_date based on day
        if day == 'today':
            # Fast ends now
            fast_end_date = timezone.now()
        else:  # yesterday
            # Fast ends at noon yesterday (12:00 PM)
            now = timezone.now()
            yesterday = now - timedelta(days=1)
            fast_end_date = timezone.make_aware(
                datetime.combine(yesterday.date(), time(12, 0))
            )

        # Generate a unique source_id for manual entries
        source_id = str(uuid.uuid4())

        fast = FastingSession.objects.create(
            source='Manual',
            source_id=source_id,
            duration=hours,
            fast_end_date=fast_end_date,
        )

        day_label = 'Today' if day == 'today' else 'Yesterday'
        return JsonResponse({
            'success': True,
            'message': f'{day_label}: {hours}-hour fast logged successfully!',
            'fast_id': fast.id,
            'duration': float(fast.duration),
            'fast_end_date': fast_end_date.strftime('%Y-%m-%d %H:%M')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error logging fast: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
def master_sync(request):
    """
    AJAX endpoint to trigger the master sync command.

    Runs the sync_all management command to sync data from all sources
    (Whoop, Withings, etc.)

    Returns JSON:
        - success: boolean
        - message: string
        - output: string (command output if successful)
    """
    try:
        # Capture command output (both stdout and stderr)
        output = StringIO()
        error_output = StringIO()

        # Run the sync_all command
        call_command('sync_all', '--days=30', stdout=output, stderr=error_output)

        output_text = output.getvalue()
        error_text = error_output.getvalue()

        # Combine both outputs
        full_output = output_text
        if error_text:
            full_output += f"\n\nErrors/Warnings:\n{error_text}"

        return JsonResponse({
            'success': True,
            'message': 'Master sync completed!',
            'output': full_output,
            'has_errors': bool(error_text)
        })

    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'Error running master sync: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)
