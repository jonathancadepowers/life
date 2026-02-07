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


def _strip_ansi(text):
    """Remove ANSI escape codes from text."""
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def _extract_sync_summary(output_text, error_text):
    """Extract the SYNC SUMMARY section from command output, or return full output."""
    summary_start = output_text.find('SYNC SUMMARY')
    if summary_start == -1:
        full_output = output_text
        if error_text:
            full_output += f"\n\nErrors/Warnings:\n{error_text}"
        return full_output

    lines = output_text[:summary_start].split('\n')
    # Go back to find the === line
    summary_start_line = len(lines) - 1
    for i in range(len(lines) - 1, -1, -1):
        if '=' * 20 in lines[i]:
            summary_start_line = i
            break

    all_lines = output_text.split('\n')
    return '\n'.join(all_lines[summary_start_line:])


def _detect_auth_errors(full_output):
    """Detect authentication errors for each service from sync output."""
    auth_errors = {}
    if 'Whoop refresh token expired' in full_output or 'python manage.py whoop_auth' in full_output:
        auth_errors['whoop'] = True

    output_lower = full_output.lower()
    withings_mentioned = 'withings' in output_lower
    withings_auth_issue = (
        'refresh token' in output_lower
        or 'python manage.py withings_auth' in full_output
        or 'invalid_token' in output_lower
        or 'access token provided is invalid' in output_lower
    )
    if withings_mentioned and withings_auth_issue:
        auth_errors['withings'] = True

    return auth_errors


@require_http_methods(["POST"])
def master_sync(_request):
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
        from workouts.models import Workout
        from weight.models import WeighIn
        from time_logs.models import TimeLog

        before_count = Workout.objects.count() + WeighIn.objects.count() + TimeLog.objects.count()

        output = StringIO()
        error_output = StringIO()
        call_command('sync_all', '--days=30', stdout=output, stderr=error_output)

        after_count = Workout.objects.count() + WeighIn.objects.count() + TimeLog.objects.count()
        new_entries = after_count - before_count

        output_text = _strip_ansi(output.getvalue())
        error_text = _strip_ansi(error_output.getvalue())

        full_output = _extract_sync_summary(output_text, error_text)
        has_errors = '\u2717' in full_output or bool(error_text)
        auth_errors = _detect_auth_errors(full_output)

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
