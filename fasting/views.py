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
    (Whoop, Withings, Toggl)

    Returns JSON:
        - success: boolean
        - message: string (with count of new entries)
        - output: string (command output if successful)
    """
    try:
        import re

        # Import models to count records
        from workouts.models import Workout
        from weight.models import WeighIn
        from time_logs.models import TimeLog

        # Count records before sync
        before_count = Workout.objects.count() + WeighIn.objects.count() + TimeLog.objects.count()

        # Capture command output (both stdout and stderr)
        output = StringIO()
        error_output = StringIO()

        # Run the sync_all command
        call_command('sync_all', '--days=30', stdout=output, stderr=error_output)

        # Count records after sync
        after_count = Workout.objects.count() + WeighIn.objects.count() + TimeLog.objects.count()
        new_entries = after_count - before_count

        output_text = output.getvalue()
        error_text = error_output.getvalue()

        # Strip ANSI escape codes from output (they don't render in HTML)
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        output_text = ansi_escape.sub('', output_text)
        error_text = ansi_escape.sub('', error_text)

        # Extract only the SYNC SUMMARY section
        summary_start = output_text.find('SYNC SUMMARY')
        if summary_start != -1:
            # Find the start of the summary box (the line with = signs before "SYNC SUMMARY")
            lines = output_text[:summary_start].split('\n')
            # Go back to find the === line
            for i in range(len(lines) - 1, -1, -1):
                if '=' * 20 in lines[i]:
                    summary_start_line = i
                    break
            else:
                summary_start_line = len(lines) - 1

            # Reconstruct from the summary section onwards
            all_lines = output_text.split('\n')
            full_output = '\n'.join(all_lines[summary_start_line:])
        else:
            # Fallback: show all output if summary not found
            full_output = output_text
            if error_text:
                full_output += f"\n\nErrors/Warnings:\n{error_text}"

        # Detect if there were any errors by checking for the ✗ symbol in the output
        has_errors = '✗' in full_output or bool(error_text)

        # Detect authentication errors and which services need re-auth
        auth_errors = {}
        if 'Whoop refresh token expired' in full_output or 'python manage.py whoop_auth' in full_output:
            auth_errors['whoop'] = True
        if 'Withings' in full_output and ('refresh token' in full_output.lower() or 'python manage.py withings_auth' in full_output):
            auth_errors['withings'] = True

        # Create message with count
        message = f'Synced {new_entries} new {"entry" if new_entries == 1 else "entries"}!'

        return JsonResponse({
            'success': True,
            'message': message,
            'output': full_output,
            'auth_errors': auth_errors,
            'has_errors': has_errors
        })

    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'Error running master sync: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)
