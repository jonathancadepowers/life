from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime, time
from .models import FastingSession
from django.core.management import call_command
from io import StringIO
import uuid
import pytz


def activity_logger(request):
    """Render the Activity Logger page.

    Note: We don't pass today's agenda in the context because we want
    JavaScript to determine "today" based on the user's browser timezone,
    not the server's timezone. JavaScript will fetch the agenda via AJAX
    on page load.
    """
    from projects.models import Project

    # Get all projects for the dropdowns
    projects = Project.objects.all().order_by('display_string')

    context = {
        'projects': projects,
        'agenda': None,  # JavaScript will fetch today's agenda based on user's timezone
    }

    return render(request, 'fasting/activity_logger.html', context)


@require_http_methods(["POST"])
def log_fast(request):
    """
    AJAX endpoint to log a new fast.

    Expects POST data:
        - hours: integer (12, 16, or 18)
        - date: string (YYYY-MM-DD format) - the date for the fast

    Returns JSON:
        - success: boolean
        - message: string
        - fast_id: integer (if successful)
    """
    try:
        # Get the fast duration and date from POST data
        hours = request.POST.get('hours')
        date_str = request.POST.get('date')

        if not hours:
            return JsonResponse({
                'success': False,
                'message': 'Fast duration is required'
            }, status=400)

        if not date_str:
            return JsonResponse({
                'success': False,
                'message': 'Date is required'
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

        # Parse the date string
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)

        # Get user's timezone from cookie (set by browser), default to America/Chicago (CST)
        user_tz_str = request.COOKIES.get('user_timezone', 'America/Chicago')
        try:
            user_tz = pytz.timezone(user_tz_str)
        except pytz.exceptions.UnknownTimeZoneError:
            user_tz = pytz.timezone('America/Chicago')

        # Fast ends at 12:00 PM (noon) on the selected date in user's timezone
        # Create a naive datetime at noon on the selected date
        fast_end_date_naive = datetime.combine(selected_date, time(12, 0))

        # Localize to user's timezone (this handles DST correctly)
        fast_end_date = user_tz.localize(fast_end_date_naive)

        # Generate a unique source_id for manual entries
        source_id = str(uuid.uuid4())

        fast = FastingSession.objects.create(
            source='Manual',
            source_id=source_id,
            duration=hours,
            fast_end_date=fast_end_date,  # This is now timezone-aware and will be stored as UTC in DB
        )

        return JsonResponse({
            'success': True,
            'message': f'{hours}-hour fast logged successfully for {selected_date.strftime("%B %d, %Y")}!',
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

        # Check for Withings auth errors (refresh token expired, invalid_token, or access token issues)
        withings_in_output = 'Withings' in full_output or 'WITHINGS' in full_output
        withings_auth_error = (
            'refresh token' in full_output.lower() or
            'python manage.py withings_auth' in full_output or
            'invalid_token' in full_output.lower() or
            'access token provided is invalid' in full_output.lower()
        )
        if withings_in_output and withings_auth_error:
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
