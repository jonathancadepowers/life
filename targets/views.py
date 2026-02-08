from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import connection
from datetime import date, datetime, timedelta
from .models import DailyAgenda
from projects.models import Project
from goals.models import Goal
from time_logs.models import TimeLog
from time_logs.services.toggl_client import TogglAPIClient
import pytz

_TIME_FORMAT = '%I:%M %p'
_DATE_FORMAT = '%b %-d, %Y'
_OBJECTIVE_NOT_FOUND = 'Objective not found'
_INVALID_JSON = 'Invalid JSON data'


class TogglRateLimitError(Exception):
    """Raised when the Toggl API rate limit is reached and no cached data is available."""


def get_user_timezone(request):
    """
    Get the user's timezone from the cookie set by JavaScript.
    Falls back to UTC if no timezone is set.
    """
    user_tz_name = request.COOKIES.get('user_timezone', 'UTC')
    try:
        return pytz.timezone(user_tz_name)
    except pytz.exceptions.UnknownTimeZoneError:
        return pytz.UTC


def get_user_today(request):
    """
    Get today's date in the user's timezone.
    Returns both the date object and timezone-aware start/end datetimes.
    """
    user_tz = get_user_timezone(request)
    now_in_user_tz = timezone.now().astimezone(user_tz)
    today = now_in_user_tz.date()

    # Create timezone-aware start and end of day in user's timezone
    today_start = user_tz.localize(datetime.combine(today, datetime.min.time()))
    today_end = user_tz.localize(datetime.combine(today, datetime.max.time()))

    return today, today_start, today_end


def set_agenda(request):
    """View to set today's agenda with 3 targets."""
    # Use user's timezone to determine "today"
    today = get_user_today(request)[0]

    if request.method == 'POST':
        # Get or create today's agenda
        agenda, _ = DailyAgenda.objects.get_or_create(date=today)

        # Process each target
        for i in range(1, 4):
            project_id = request.POST.get(f'project_{i}')
            goal_id = request.POST.get(f'goal_{i}')
            target_input = request.POST.get(f'target_{i}')

            if project_id and goal_id and target_input:
                # Set agenda fields directly with text
                setattr(agenda, f'project_{i}_id', project_id)
                setattr(agenda, f'goal_{i}_id', goal_id)
                setattr(agenda, f'target_{i}', target_input)

        agenda.save()
        return redirect('set_agenda')

    # Get today's agenda if it exists
    try:
        agenda = DailyAgenda.objects.get(date=today)
    except DailyAgenda.DoesNotExist:
        agenda = None

    # Get all projects for dropdowns
    projects = Project.objects.all()

    context = {
        'today': today,
        'agenda': agenda,
        'projects': projects,
    }

    return render(request, 'targets/set_agenda.html', context)


def get_goals_for_project(request):
    """AJAX endpoint to get goals associated with a project."""
    project_id = request.GET.get('project_id')
    show_all = request.GET.get('all', 'false').lower() == 'true'

    if not project_id and not show_all:
        return JsonResponse({'goals': []})

    if show_all:
        # Return all goals from database (useful after syncing from Toggl)
        goals = Goal.objects.all().values('goal_id', 'display_string')
    else:
        # Find goals that have been used with this project in time logs
        goal_ids = TimeLog.objects.filter(
            project_id=project_id
        ).values_list('goals__goal_id', flat=True).distinct()

        goals = Goal.objects.filter(goal_id__in=goal_ids).values('goal_id', 'display_string')

    return JsonResponse({'goals': list(goals)})


@require_http_methods(["POST"])
def sync_toggl_projects_goals(_request):
    """AJAX endpoint to sync Projects and Goals from Toggl."""
    try:
        # Initialize Toggl client
        toggl_client = TogglAPIClient()

        # Fetch projects from Toggl
        toggl_projects = toggl_client.get_projects()
        projects_synced = 0

        for project_data in toggl_projects:
            # Toggl projects have 'id' and 'name' fields
            project_id = project_data.get('id')
            project_name = project_data.get('name')

            if project_id and project_name:
                # Update or create project in database
                Project.objects.update_or_create(
                    project_id=project_id,
                    defaults={'display_string': project_name}
                )
                projects_synced += 1

        # Fetch tags (goals) from Toggl
        toggl_tags = toggl_client.get_tags()
        goals_synced = 0

        for tag_data in toggl_tags:
            # Toggl tags have 'id' and 'name' fields
            tag_id = tag_data.get('id')
            tag_name = tag_data.get('name')

            if tag_id and tag_name:
                # Update or create goal in database
                # goal_id stores the Toggl tag ID, display_string stores the tag name
                Goal.objects.update_or_create(
                    goal_id=str(tag_id),  # Use Toggl tag ID as primary key
                    defaults={'display_string': tag_name}
                )
                goals_synced += 1

        # Return updated lists
        projects = list(Project.objects.all().values('project_id', 'display_string'))
        goals = list(Goal.objects.all().values('goal_id', 'display_string'))

        return JsonResponse({
            'success': True,
            'message': f'Synced {projects_synced} projects and {goals_synced} goals from Toggl',
            'projects': projects,
            'goals': goals
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error syncing from Toggl: {str(e)}'
        }, status=500)


def _compute_day_score(agenda):
    """Calculate the overall day score from targets 1-3 on an agenda."""
    targets_set = 0
    total_score = 0

    for i in range(1, 4):
        target = getattr(agenda, f'target_{i}')
        target_score = getattr(agenda, f'target_{i}_score')
        if target:
            targets_set += 1
            if target_score is not None:
                total_score += target_score

    return total_score / targets_set if targets_set > 0 else None


def _apply_agenda_target(agenda, i, post_data):
    """Set or clear a single target (i) on the agenda from POST data."""
    project_id = post_data.get(f'project_{i}')
    goal_id = post_data.get(f'goal_{i}')
    target_input = post_data.get(f'target_{i}')

    if project_id and target_input:
        setattr(agenda, f'project_{i}_id', project_id)
        setattr(agenda, f'goal_{i}_id', goal_id if goal_id else None)
        setattr(agenda, f'target_{i}', target_input)
    else:
        setattr(agenda, f'project_{i}_id', None)
        setattr(agenda, f'goal_{i}_id', None)
        setattr(agenda, f'target_{i}', '')
        setattr(agenda, f'target_{i}_score', None)


@require_http_methods(["POST"])
def save_agenda(request):
    """AJAX endpoint to save agenda for a specific date (or today if not specified)."""
    try:
        date_str = request.POST.get('date')
        if date_str:
            from datetime import datetime
            agenda_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            agenda_date = get_user_today(request)[0]

        agenda, _ = DailyAgenda.objects.get_or_create(date=agenda_date)

        for i in range(1, 4):
            _apply_agenda_target(agenda, i, request.POST)

        agenda.other_plans = request.POST.get('other_plans', '')
        agenda.day_score = _compute_day_score(agenda)
        agenda.save()

        return JsonResponse({
            'success': True,
            'message': 'Today\'s agenda has been set!',
            'day_score': agenda.day_score
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error saving agenda: {str(e)}'
        }, status=500)


def _resolve_goal_tag_name(goal_id):
    """Convert a goal_id to the corresponding Toggl tag name, or None."""
    if not goal_id:
        return None
    try:
        return Goal.objects.get(goal_id=goal_id).display_string
    except Goal.DoesNotExist:
        return None


def _compute_today_start_utc(now, timezone_offset):
    """Compute the UTC timestamp for the start of today using JS timezone offset."""
    if timezone_offset:
        offset_minutes = int(timezone_offset)
        offset_delta = timedelta(minutes=-offset_minutes)
        local_now = now + offset_delta
        local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        return local_midnight - offset_delta
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _fetch_toggl_entries_cached(today_start, now):
    """Fetch Toggl time entries with caching to respect API rate limits."""
    from time_logs.services.toggl_client import TogglAPIClient
    from django.core.cache import cache

    five_min_interval = now.minute // 5
    cache_key = f"toggl_entries_{today_start.date()}_{now.hour}_{five_min_interval}"

    time_entries = cache.get(cache_key)
    if time_entries is not None:
        return time_entries

    try:
        client = TogglAPIClient()
        time_entries = client.get_time_entries(start_date=today_start, end_date=now)
        cache.set(cache_key, time_entries, 60)
        return time_entries
    except Exception as api_error:
        error_str = str(api_error)
        if '402' in error_str or '429' in error_str or 'rate' in error_str.lower():
            time_entries = cache.get(cache_key, [])
            if not time_entries:
                raise TogglRateLimitError("Toggl API rate limit reached. Please wait a moment and refresh.")
            return time_entries
        raise


def _filter_toggl_entries(time_entries, project_id, goal_tag_name, now):
    """Filter Toggl API entries by project and tag, returning total_seconds and debug entries."""
    total_seconds = 0
    matched_entries = []

    for entry in time_entries:
        if str(entry.get('project_id')) != str(project_id):
            continue
        if goal_tag_name and goal_tag_name not in entry.get('tags', []):
            continue

        entry_duration = entry.get('duration', 0)
        entry_start = entry.get('start')
        is_running = entry_duration < 0

        if is_running and entry_start:
            start_dt = datetime.fromisoformat(entry_start.replace('Z', '+00:00'))
            entry_duration = int((now - start_dt).total_seconds())

        total_seconds += entry_duration
        matched_entries.append({
            'start': entry_start,
            'duration_seconds': entry_duration,
            'is_running': is_running,
            'tags': entry.get('tags', [])
        })

    return total_seconds, matched_entries


def _query_toggl_today(project_id, goal_tag_name, timezone_offset, now):
    """Query Toggl API for today's time data, returning total_seconds and debug_info."""
    today_start = _compute_today_start_utc(now, timezone_offset)
    time_entries = _fetch_toggl_entries_cached(today_start, now)
    total_seconds, matched_entries = _filter_toggl_entries(time_entries, project_id, goal_tag_name, now)

    debug_info = {
        'query_start': today_start.isoformat(),
        'query_end': now.isoformat(),
        'timezone_offset': timezone_offset or 'UTC (not provided)',
        'source': 'toggl_api',
        'entries_count': len(matched_entries),
        'entries': matched_entries
    }
    return total_seconds, debug_info


def _compute_day_boundaries_utc(target_date, timezone_offset, request):
    """Compute UTC day start/end boundaries for a past date."""
    from datetime import datetime as dt

    if timezone_offset:
        offset_minutes = int(timezone_offset)
        offset_delta = timedelta(minutes=-offset_minutes)
        target_datetime = dt.combine(target_date, dt.min.time())
        target_datetime_utc = timezone.make_aware(target_datetime)
        local_midnight = target_datetime_utc + offset_delta
        next_local_midnight = local_midnight + timedelta(days=1)
        return local_midnight - offset_delta, next_local_midnight - offset_delta

    user_tz_str = request.COOKIES.get('user_timezone', 'UTC')
    try:
        user_tz = pytz.timezone(user_tz_str)
    except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
        user_tz = pytz.UTC

    day_start_utc = user_tz.localize(dt.combine(target_date, dt.min.time()))
    return day_start_utc, day_start_utc + timedelta(days=1)


def _query_toggl_historical(project_id, goal_id, target_date, timezone_offset, request):
    """Query database for historical time log data, returning total_seconds and debug_info."""
    from time_logs.models import TimeLog

    day_start_utc, day_end_utc = _compute_day_boundaries_utc(target_date, timezone_offset, request)

    time_logs = TimeLog.objects.filter(
        project_id=int(project_id),
        start__gte=day_start_utc,
        start__lt=day_end_utc
    )
    if goal_id:
        time_logs = time_logs.filter(goals__goal_id=goal_id).distinct()

    total_seconds = 0
    matched_entries = []
    for log in time_logs:
        duration = (log.end - log.start).total_seconds()
        total_seconds += duration
        matched_entries.append({
            'start': log.start.isoformat(),
            'end': log.end.isoformat(),
            'duration_seconds': int(duration),
            'source': log.source
        })

    debug_info = {
        'query_start': day_start_utc.isoformat(),
        'query_end': day_end_utc.isoformat(),
        'timezone_offset': timezone_offset or 'UTC (not provided)',
        'source': 'database',
        'target_date': target_date.isoformat(),
        'entries_count': len(matched_entries),
        'entries': matched_entries
    }
    return total_seconds, debug_info


def _format_time_display(total_seconds):
    """Convert seconds to a human-readable hours/minutes display string."""
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    display = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
    return hours, minutes, display


def get_toggl_time_today(request):
    """
    AJAX endpoint to get time spent on a project (and optionally a goal/tag).
    - For today: pulls from Toggl API (includes running timers)
    - For past dates: pulls from database (historical data)
    """
    try:
        project_id = request.GET.get('project_id')
        goal_id = request.GET.get('goal_id')
        timezone_offset = request.GET.get('timezone_offset')
        date_str = request.GET.get('date')

        if not project_id:
            return JsonResponse({'error': 'project_id is required'}, status=400)

        goal_tag_name = _resolve_goal_tag_name(goal_id)
        now = timezone.now()

        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            is_today = (target_date == now.date())
        else:
            target_date = now.date()
            is_today = True

        if is_today:
            total_seconds, debug_info = _query_toggl_today(project_id, goal_tag_name, timezone_offset, now)
        else:
            total_seconds, debug_info = _query_toggl_historical(project_id, goal_id, target_date, timezone_offset, request)

        hours, minutes, time_display = _format_time_display(total_seconds)

        return JsonResponse({
            'success': True,
            'total_seconds': total_seconds,
            'hours': hours,
            'minutes': minutes,
            'display': time_display,
            'debug': debug_info
        })

    except Exception as e:
        import traceback
        print(f"Error in get_toggl_time_today: {traceback.format_exc()}")

        error_msg = str(e)
        if '402' in error_msg or 'Payment Required' in error_msg:
            error_msg = "Toggl API payment required - please check your Toggl subscription"

        return JsonResponse({
            'success': False,
            'error': error_msg
        }, status=500)


def get_available_agenda_dates(_request):
    """
    AJAX endpoint to get all dates that have agendas in the database.
    Returns list of dates in ISO format (YYYY-MM-DD).
    """
    try:
        # Get all unique dates that have agendas
        dates = DailyAgenda.objects.values_list('date', flat=True).order_by('-date')

        # Convert to ISO format strings
        date_strings = [date.isoformat() for date in dates]

        return JsonResponse({
            'success': True,
            'dates': date_strings
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def get_agenda_for_date(request):
    """
    AJAX endpoint to get agenda for a specific date.
    Expects GET parameter 'date' in ISO format (YYYY-MM-DD).
    """
    try:
        date_str = request.GET.get('date')

        if not date_str:
            return JsonResponse({
                'success': False,
                'error': 'Date parameter is required'
            }, status=400)

        # Parse the date
        from datetime import datetime
        agenda_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Get the agenda for this date
        try:
            agenda = DailyAgenda.objects.get(date=agenda_date)

            # Build response data
            agenda_data = {
                'date': agenda.date.isoformat(),
                'target_1_score': agenda.target_1_score,
                'target_2_score': agenda.target_2_score,
                'target_3_score': agenda.target_3_score,
                'day_score': agenda.day_score,
                'other_plans': agenda.other_plans,
                'targets': []
            }

            # Add each target's data
            for i in range(1, 4):
                project = getattr(agenda, f'project_{i}')
                goal = getattr(agenda, f'goal_{i}')
                target_text = getattr(agenda, f'target_{i}')

                target_data = {
                    'project_id': project.project_id if project else None,
                    'project_name': project.display_string if project else None,
                    'goal_id': goal.goal_id if goal else None,
                    'goal_name': goal.display_string if goal else None,
                    'target_id': target_text,  # Just the text now
                    'target_name': target_text  # Just the text now
                }

                agenda_data['targets'].append(target_data)

            return JsonResponse({
                'success': True,
                'agenda': agenda_data
            })

        except DailyAgenda.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'No agenda found for this date'
            }, status=404)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def _validate_target_num(raw_value):
    """Validate and return target_num as int, or None if invalid."""
    try:
        target_num = int(raw_value)
        return target_num if target_num in (1, 2, 3, 4) else None
    except (ValueError, TypeError):
        return None


def _validate_score(raw_value):
    """Validate and return score as float or None. Returns (score, is_valid)."""
    if raw_value == 'null':
        return None, True
    try:
        score = float(raw_value)
        return (score, True) if score in (0, 0.5, 1) else (None, False)
    except (ValueError, TypeError):
        return None, False


@require_http_methods(["POST"])
def save_target_score(request):
    """
    AJAX endpoint to save a score for a specific target on a specific date.

    Expects POST data:
        - date: string (YYYY-MM-DD) - the date of the agenda
        - target_num: integer (1, 2, or 3) - which target to score
        - score: float (0, 0.5, or 1) - the score value
    """
    try:
        date_str = request.POST.get('date')
        raw_target_num = request.POST.get('target_num')
        raw_score = request.POST.get('score')

        if not date_str or not raw_target_num or raw_score is None:
            return JsonResponse({'success': False, 'error': 'Missing required parameters'}, status=400)

        target_num = _validate_target_num(raw_target_num)
        if target_num is None:
            return JsonResponse({'success': False, 'error': 'target_num must be 1, 2, 3, or 4'}, status=400)

        score, score_valid = _validate_score(raw_score)
        if not score_valid:
            return JsonResponse({'success': False, 'error': 'score must be 0, 0.5, 1, or null'}, status=400)

        if target_num not in (1, 2, 3):
            return JsonResponse({
                'success': False,
                'error': f'Invalid target number: {target_num}. Only targets 1-3 can be scored.'
            }, status=400)

        from datetime import datetime as dt
        agenda_date = dt.strptime(date_str, '%Y-%m-%d').date()

        try:
            agenda = DailyAgenda.objects.get(date=agenda_date)
        except DailyAgenda.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'No agenda found for this date'}, status=404)

        setattr(agenda, f'target_{target_num}_score', score)
        agenda.day_score = _compute_day_score(agenda)
        agenda.save()

        return JsonResponse({
            'success': True,
            'message': f'Score saved for target {target_num}',
            'day_score': agenda.day_score
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def _parse_report_date_range(request):
    """Parse date range from query params or default to current week."""
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        today = get_user_today(request)[0]
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)

    user_tz = get_user_timezone(request)
    start_datetime = user_tz.localize(datetime.combine(start_date, datetime.min.time()))
    end_datetime = user_tz.localize(datetime.combine(end_date, datetime.max.time()))
    days_in_range = (end_date - start_date).days + 1

    return start_date, end_date, start_datetime, end_datetime, days_in_range, user_tz


def _get_fasting_stats(start_datetime, end_datetime, days_in_range):
    """Gather fasting statistics for the given date range."""
    from django.db.models import Sum, Avg, Max
    from django.db.models.functions import TruncDate
    from fasting.models import FastingSession

    fasting_sessions = FastingSession.objects.filter(
        fast_end_date__gte=start_datetime,
        fast_end_date__lte=end_datetime
    )
    days_with_fasts = fasting_sessions.annotate(
        fast_date=TruncDate('fast_end_date')
    ).values('fast_date').distinct().count()

    return {
        'count': fasting_sessions.count(),
        'avg_duration': fasting_sessions.aggregate(Avg('duration'))['duration__avg'] or 0,
        'max_duration': fasting_sessions.aggregate(Max('duration'))['duration__max'] or 0,
        'total_hours': fasting_sessions.aggregate(Sum('duration'))['duration__sum'] or 0,
        'year_count': FastingSession.objects.count(),
        'percent_days_fasted': round((days_with_fasts / days_in_range * 100), 1) if days_in_range > 0 else 0,
    }


def _get_nutrition_stats(start_datetime, end_datetime, days_in_range):
    """Gather nutrition statistics for the given date range."""
    from django.db.models import Sum
    from nutrition.models import NutritionEntry

    nutrition_entries = NutritionEntry.objects.filter(
        consumption_date__gte=start_datetime,
        consumption_date__lte=end_datetime
    )
    days_tracked = nutrition_entries.values('consumption_date__date').distinct().count()

    nutrition_agg = nutrition_entries.aggregate(
        total_calories=Sum('calories'),
        total_protein=Sum('protein'),
        total_carbs=Sum('carbs'),
        total_fat=Sum('fat'),
    )

    def _avg(field):
        return float(nutrition_agg[field] or 0) / days_tracked if days_tracked > 0 else 0

    return {
        'days_tracked': days_tracked,
        'days_in_range': days_in_range,
        'percent_tracked': round((days_tracked / days_in_range * 100), 1) if days_in_range > 0 else 0,
        'avg_calories': _avg('total_calories'),
        'avg_protein': _avg('total_protein'),
        'avg_carbs': _avg('total_carbs'),
        'avg_fat': _avg('total_fat'),
    }


def _get_weight_stats(start_datetime, end_datetime):
    """Gather weight statistics for the given date range."""
    from django.db.models import Avg
    from weight.models import WeighIn

    weigh_ins = WeighIn.objects.filter(
        measurement_time__gte=start_datetime,
        measurement_time__lte=end_datetime
    ).order_by('measurement_time')

    stats = {
        'count': weigh_ins.count(),
        'start_weight': None,
        'end_weight': None,
        'change': None,
        'avg_weight': None,
        'year_change': None
    }

    if not weigh_ins.exists():
        return stats

    stats['start_weight'] = float(weigh_ins.first().weight)
    stats['end_weight'] = float(weigh_ins.last().weight)
    stats['change'] = stats['end_weight'] - stats['start_weight']
    stats['avg_weight'] = float(weigh_ins.aggregate(Avg('weight'))['weight__avg'])

    earliest_weigh_in = WeighIn.objects.order_by('measurement_time').first()
    if earliest_weigh_in:
        stats['year_change'] = stats['end_weight'] - float(earliest_weigh_in.weight)

    return stats


def _get_workouts_by_sport(start_datetime, end_datetime, sport_names_dict):
    """Group workouts by sport and compute per-sport statistics."""
    from workouts.models import Workout

    workouts = Workout.objects.filter(
        start__gte=start_datetime,
        start__lte=end_datetime
    )

    workouts_by_sport = {}
    for workout in workouts:
        sport_id = 233 if workout.sport_id == -1 else workout.sport_id
        sport_name = sport_names_dict.get(sport_id, f'Sport {sport_id}')

        if sport_name not in workouts_by_sport:
            workouts_by_sport[sport_name] = {
                'count': 0,
                'total_calories': 0,
                'total_seconds': 0,
                'total_hours': 0,
                'avg_heart_rate': []
            }

        entry = workouts_by_sport[sport_name]
        entry['count'] += 1
        if workout.calories_burned:
            entry['total_calories'] += float(workout.calories_burned)
        if workout.end:
            entry['total_seconds'] += (workout.end - workout.start).total_seconds()
        if workout.average_heart_rate:
            entry['avg_heart_rate'].append(workout.average_heart_rate)

    for sport_data in workouts_by_sport.values():
        sport_data['total_hours'] = round(sport_data['total_seconds'] / 3600, 1)
        hr_list = sport_data['avg_heart_rate']
        sport_data['avg_heart_rate'] = round(sum(hr_list) / len(hr_list)) if hr_list else 0
        del sport_data['total_seconds']

    return dict(sorted(
        workouts_by_sport.items(),
        key=lambda x: x[1]['count'],
        reverse=True
    ))


def _resolve_project_name(project_id):
    """Resolve a project_id to its display name, falling back to a generic label."""
    try:
        return Project.objects.get(project_id=project_id).display_string
    except Project.DoesNotExist:
        return f"Project {project_id}"


def _accumulate_time_by_project(time_logs):
    """Accumulate hours per project and goal from time log entries."""
    time_by_project = {}
    for log in time_logs:
        project_name = _resolve_project_name(log.project_id)
        duration_hours = (log.end - log.start).total_seconds() / 3600

        if project_name not in time_by_project:
            time_by_project[project_name] = {'total_hours': 0, 'goals': {}}

        time_by_project[project_name]['total_hours'] += duration_hours
        for goal in log.goals.all():
            goals = time_by_project[project_name]['goals']
            goals[goal.display_string] = goals.get(goal.display_string, 0) + duration_hours
    return time_by_project


def _apply_time_percentages(time_by_project, total_time_hours):
    """Add percentage fields to each project and goal entry."""
    for project_data in time_by_project.values():
        project_data['percentage'] = round((project_data['total_hours'] / total_time_hours) * 100) if total_time_hours > 0 else 0
        project_data['goals'] = {
            name: {
                'hours': hours,
                'percentage': round((hours / total_time_hours) * 100) if total_time_hours > 0 else 0,
            }
            for name, hours in project_data['goals'].items()
        }


def _get_time_by_project(start_datetime, end_datetime):
    """Group time logs by project and goal, returning sorted data with percentages."""
    time_logs = TimeLog.objects.filter(
        start__gte=start_datetime,
        start__lte=end_datetime
    ).prefetch_related('goals')

    time_by_project = _accumulate_time_by_project(time_logs)

    # Sort projects and goals by hours descending
    time_by_project = dict(sorted(
        time_by_project.items(), key=lambda x: x[1]['total_hours'], reverse=True
    ))
    for project_name in time_by_project:
        time_by_project[project_name]['goals'] = dict(sorted(
            time_by_project[project_name]['goals'].items(), key=lambda x: x[1], reverse=True
        ))

    total_time_hours = sum(pd['total_hours'] for pd in time_by_project.values())
    _apply_time_percentages(time_by_project, total_time_hours)

    return time_by_project, total_time_hours


def _calculate_today_result_for_objective(obj, today, today_start, today_end):
    """Execute a modified SQL query scoped to today's date for a single objective."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        with connection.cursor() as cursor:
            sql = obj.objective_definition.strip()

            date_columns = ['consumption_date', 'fast_end_date', 'measurement_time', 'start', 'created_at', 'date']
            date_col = None
            for col in date_columns:
                if col in sql.lower():
                    date_col = col
                    break

            if not date_col:
                return 0

            sql_upper = sql.upper()
            insert_pos = len(sql)
            for keyword in ['GROUP BY', 'ORDER BY', 'LIMIT', 'OFFSET']:
                pos = sql_upper.find(keyword)
                if 0 < pos < insert_pos:
                    insert_pos = pos

            if date_col == 'date':
                date_filter = f"\nAND {date_col} = '{today.isoformat()}'\n"
            else:
                date_filter = f"\nAND {date_col} >= '{today_start.isoformat()}' AND {date_col} < '{today_end.isoformat()}'\n"

            modified_sql = sql[:insert_pos].rstrip() + " " + date_filter + sql[insert_pos:]
            cursor.execute(modified_sql)
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0])
    except Exception as e:
        logger.warning(f"Could not calculate today's result for '{obj.label}': {e}")

    return 0


def _build_objective_data(obj, today, today_start, today_end):
    """Build the template data dict for a single monthly objective."""
    from calendar import monthrange

    result = obj.result if obj.result is not None else 0
    today_result = _calculate_today_result_for_objective(obj, today, today_start, today_end)

    progress_pct = (result / obj.objective_value) * 100 if result is not None and obj.objective_value > 0 else 0

    days_in_month = monthrange(obj.start.year, obj.start.month)[1]
    weeks_in_month = days_in_month / 7.0
    target_per_week = obj.objective_value / weeks_in_month if weeks_in_month > 0 else 0
    remaining = max(0, obj.objective_value - (result if result is not None else 0))

    return {
        'objective_id': obj.objective_id,
        'label': obj.label,
        'description': obj.description,
        'start': obj.start,
        'target': obj.objective_value,
        'result': result if result is not None else 0,
        'today_result': round(today_result, 1),
        'progress_pct': round(progress_pct, 1),
        'achieved': result is not None and result >= obj.objective_value,
        'objective_value': obj.objective_value,
        'objective_definition': obj.objective_definition,
        'category': obj.category,
        'target_per_week': round(target_per_week, 1),
        'days_in_month': days_in_month,
        'remaining': round(remaining, 1),
        'unit': obj.unit_of_measurement,
        'historical_display': obj.historical_display,
    }


def _refresh_objective_results(monthly_objectives):
    """Re-execute SQL definitions and update cached results for each objective."""
    for obj in monthly_objectives:
        try:
            with connection.cursor() as cursor:
                cursor.execute(obj.objective_definition)
                row = cursor.fetchone()
                obj.result = float(row[0]) if row and row[0] is not None else 0.0
                obj.save(update_fields=['result'])
        except Exception:
            if obj.result is None:
                obj.result = 0.0
                obj.save(update_fields=['result'])


def _get_monthly_objectives_context(request, end_date, start_date):
    """Build the full monthly objectives context dict."""
    from monthly_objectives.models import MonthlyObjective
    from calendar import monthrange
    from collections import defaultdict

    crosses_months = (start_date.year != end_date.year) or (start_date.month != end_date.month)

    target_month_first_day = end_date.replace(day=1)
    last_day = monthrange(end_date.year, end_date.month)[1]
    target_month_last_day = end_date.replace(day=last_day)

    monthly_objectives = MonthlyObjective.objects.filter(
        start=target_month_first_day,
        end=target_month_last_day
    ).order_by('label')

    _refresh_objective_results(monthly_objectives)

    today, today_start, today_end = get_user_today(request)
    objectives_data = [_build_objective_data(obj, today, today_start, today_end) for obj in monthly_objectives]

    # Group by category
    objectives_by_category = defaultdict(list)
    uncategorized = []
    for obj in objectives_data:
        if obj['category']:
            objectives_by_category[obj['category']].append(obj)
        else:
            uncategorized.append(obj)

    category_config = {
        'Exercise': {'icon': 'bi-lightning-charge-fill', 'color': 'danger'},
        'Nutrition': {'icon': 'bi-egg-fried', 'color': 'success'},
        'Weight': {'icon': 'bi-speedometer2', 'color': 'info'},
        'Time Mgmt': {'icon': 'bi-clock-fill', 'color': 'warning'},
    }

    predefined_order = ['Exercise', 'Nutrition', 'Weight', 'Time Mgmt']
    all_categories = [cat for cat in predefined_order if objectives_by_category.get(cat)]
    all_categories.extend(sorted(cat for cat in objectives_by_category if cat not in predefined_order))

    return {
        'objectives': objectives_data,
        'objectives_by_category': dict(objectives_by_category),
        'uncategorized': uncategorized,
        'category_config': category_config,
        'all_categories': all_categories,
        'target_month': end_date.strftime('%b %Y').upper(),
        'crosses_months': crosses_months,
    }


def _get_todays_activity(request, sport_names_dict):
    """Gather all of today's activity data for the report."""
    import json
    from fasting.models import FastingSession
    from nutrition.models import NutritionEntry
    from weight.models import WeighIn
    from workouts.models import Workout

    _today, today_start, today_end = get_user_today(request)

    todays_time_logs = TimeLog.objects.filter(
        start__gte=today_start, start__lte=today_end
    ).prefetch_related('goals').order_by('-start')

    time_logs_json = []
    for log in todays_time_logs:
        try:
            project = Project.objects.get(project_id=log.project_id)
            project_name = project.display_string
        except Project.DoesNotExist:
            project_name = f"Project {log.project_id}"
        duration = (log.end - log.start).total_seconds() if log.end else 0
        time_logs_json.append({'project': project_name, 'duration': duration})

    return {
        'workouts': Workout.objects.filter(start__gte=today_start, start__lte=today_end).order_by('-start'),
        'time_logs': todays_time_logs,
        'time_logs_json': json.dumps(time_logs_json),
        'fasts': FastingSession.objects.filter(fast_end_date__gte=today_start, fast_end_date__lte=today_end).order_by('-fast_end_date'),
        'nutrition': NutritionEntry.objects.filter(consumption_date__gte=today_start, consumption_date__lte=today_end).order_by('-consumption_date'),
        'weighins': WeighIn.objects.filter(measurement_time__gte=today_start, measurement_time__lte=today_end).order_by('-measurement_time'),
        'sport_names': sport_names_dict,
    }


def activity_report(request):
    """View for activity summary report across a date range."""
    from external_data.models import WhoopSportId

    sport_names_dict = {sport.sport_id: sport.sport_name for sport in WhoopSportId.objects.all()}
    start_date, end_date, start_datetime, end_datetime, days_in_range, user_tz = _parse_report_date_range(request)

    time_by_project, total_time_hours = _get_time_by_project(start_datetime, end_datetime)

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'days_in_range': days_in_range,
        'fasting': _get_fasting_stats(start_datetime, end_datetime, days_in_range),
        'nutrition': _get_nutrition_stats(start_datetime, end_datetime, days_in_range),
        'weight': _get_weight_stats(start_datetime, end_datetime),
        'workouts_by_sport': _get_workouts_by_sport(start_datetime, end_datetime, sport_names_dict),
        'time_by_project': time_by_project,
        'total_time_hours': round(total_time_hours, 1),
        'monthly_objectives': _get_monthly_objectives_context(request, end_date, start_date),
        'todays_activity': _get_todays_activity(request, sport_names_dict),
        'today': get_user_today(request)[0],
        'user_timezone': user_tz,
    }

    return render(request, 'targets/activity_report.html', context)


def _format_template_value(value):
    """Format a value for display in a details template."""
    from decimal import Decimal

    if not isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float) and value.is_integer():
        return f'{int(value):,}'
    return f'{value:,}'


def parse_details_template(template, data_dict):
    """
    Parse a details display template and replace {field_name} placeholders with actual values.

    Args:
        template: String template with {field_name} placeholders
        data_dict: Dictionary of field names to values

    Returns:
        Parsed string with placeholders replaced
    """
    import re

    if not template:
        return ''

    result = template
    # Find all {field_name} placeholders
    placeholders = re.findall(r'\{(\w+)\}', template)

    for placeholder in placeholders:
        value = data_dict.get(placeholder, '')
        if value is not None:
            formatted_value = _format_template_value(value)
            result = result.replace(f'{{{placeholder}}}', formatted_value)

    return result


def _fetch_workout_records(day_start, day_end, user_tz, sql_query):
    """Fetch workout records for a given day."""
    import re
    from workouts.models import Workout

    sport_match = re.search(r'sport_id\s*=\s*(\d+)', sql_query, re.IGNORECASE)
    query = Workout.objects.filter(start__gte=day_start, start__lte=day_end)
    if sport_match:
        query = query.filter(sport_id=int(sport_match.group(1)))

    return [{
        'start': w.start.astimezone(user_tz).strftime(_TIME_FORMAT),
        'end': w.end.astimezone(user_tz).strftime(_TIME_FORMAT),
        'sport_id': w.sport_id,
        'average_heart_rate': w.average_heart_rate,
        'max_heart_rate': w.max_heart_rate,
        'calories_burned': w.calories_burned,
        'distance_in_miles': w.distance_in_miles,
    } for w in query]


def _fetch_fasting_records(day_start, day_end, user_tz):
    """Fetch fasting session records for a given day."""
    from fasting.models import FastingSession
    return [{
        'duration': f.duration,
        'fast_end_date': f.fast_end_date.astimezone(user_tz).strftime(_TIME_FORMAT),
    } for f in FastingSession.objects.filter(fast_end_date__gte=day_start, fast_end_date__lte=day_end)]


def _fetch_writing_records(current_date):
    """Fetch writing log records for a given date."""
    from writing.models import WritingLog
    return [{
        'log_date': log.log_date.strftime(_DATE_FORMAT),
        'duration': log.duration,
    } for log in WritingLog.objects.filter(log_date=current_date)]


def _fetch_weight_records(day_start, day_end, user_tz):
    """Fetch weigh-in records for a given day."""
    from weight.models import WeighIn
    return [{
        'measurement_time': w.measurement_time.astimezone(user_tz).strftime(_TIME_FORMAT),
        'weight': w.weight,
    } for w in WeighIn.objects.filter(measurement_time__gte=day_start, measurement_time__lte=day_end)]


def _fetch_nutrition_records(day_start, day_end, user_tz):
    """Fetch nutrition entry records for a given day."""
    from nutrition.models import NutritionEntry
    return [{
        'consumption_date': e.consumption_date.astimezone(user_tz).strftime('%b %-d'),
        'calories': e.calories,
        'fat': e.fat,
        'carbs': e.carbs,
        'protein': e.protein,
    } for e in NutritionEntry.objects.filter(consumption_date__gte=day_start, consumption_date__lte=day_end)]


def _fetch_youtube_records(current_date):
    """Fetch YouTube avoidance log records for a given date."""
    from youtube_avoidance.models import YouTubeAvoidanceLog
    return [{
        'log_date': log.log_date.strftime(_DATE_FORMAT),
    } for log in YouTubeAvoidanceLog.objects.filter(log_date=current_date)]


def _fetch_waist_records(current_date):
    """Fetch waist circumference measurement records for a given date."""
    from waist_measurements.models import WaistCircumferenceMeasurement
    return [{
        'log_date': m.log_date.strftime(_DATE_FORMAT),
        'measurement': m.measurement,
    } for m in WaistCircumferenceMeasurement.objects.filter(log_date=current_date)]


def get_column_data(column_name, day_start, day_end, current_date, user_tz, sql_query):
    """
    Fetch all data records for a specific column and day using the configured SQL query.

    Returns a list of dictionaries (one per record), or empty list if no data found.
    """
    import re

    try:
        table_match = re.search(r'FROM\s+(\w+)', sql_query, re.IGNORECASE)
        if not table_match:
            return []

        table_name = table_match.group(1)

        _TABLE_FETCHERS = {
            'workouts_workout': lambda: _fetch_workout_records(day_start, day_end, user_tz, sql_query),
            'fasting_fastingsession': lambda: _fetch_fasting_records(day_start, day_end, user_tz),
            'writing_logs': lambda: _fetch_writing_records(current_date),
            'weight_weighin': lambda: _fetch_weight_records(day_start, day_end, user_tz),
            'nutrition_nutritionentry': lambda: _fetch_nutrition_records(day_start, day_end, user_tz),
            'youtube_avoidance_logs': lambda: _fetch_youtube_records(current_date),
            'waist_circumference_measurements': lambda: _fetch_waist_records(current_date),
        }

        fetcher = _TABLE_FETCHERS.get(table_name)
        return fetcher() if fetcher else []

    except Exception as e:
        print(f"Error fetching data for {column_name}: {e}")
        return []


def _parse_tracker_week_range(request):
    """Parse the week date range from request, capping at current week."""
    start_date_str = request.GET.get('start_date')
    today = get_user_today(request)[0]
    current_week_start = today - timedelta(days=today.weekday())

    if start_date_str:
        selected_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        start_date = selected_date - timedelta(days=selected_date.weekday())
        if start_date > current_week_start:
            start_date = current_week_start
    else:
        start_date = current_week_start

    return start_date, start_date + timedelta(days=6), current_week_start


def _get_active_columns_for_week(start_date):
    """Return columns that are active on at least one day of the week."""
    from settings.models import LifeTrackerColumn

    columns = []
    for col in LifeTrackerColumn.objects.all():
        check_date = start_date
        for _ in range(7):
            if col.is_active_on(check_date):
                columns.append(col)
                break
            check_date += timedelta(days=1)
    return columns


def _prepare_sql_params(query, current_date, day_start, day_end):
    """Replace named SQL parameters with positional ones and return (query, params)."""
    params = []
    if ':current_date' in query:
        query = query.replace(':current_date', '%s')
        params.append(current_date)
    elif ':day_start' in query or ':day_end' in query:
        query = query.replace(':day_start', '%s').replace(':day_end', '%s')
        params.extend([day_start, day_end])
    elif ':day' in query:
        query = query.replace(':day', '%s')
        params.append(current_date)
    return query, params


def _is_eat_clean_hidden(col_name, current_date, user_tz):
    """Return True if eat_clean data should be hidden (before 6 PM on that day)."""
    if col_name != 'eat_clean':
        return False
    now_in_user_tz = datetime.now(user_tz)
    six_pm = user_tz.localize(datetime.combine(current_date, datetime.min.time().replace(hour=18)))
    return now_in_user_tz < six_pm


def _build_column_details(column, day_start, day_end, current_date, user_tz):
    """Build the details string for a column with data."""
    records = get_column_data(column.column_name, day_start, day_end, current_date, user_tz, column.sql_query)
    if not records:
        return ''
    parsed_details = [parse_details_template(column.details_display, record) for record in records]
    return ', '.join(parsed_details)


def _query_column_for_day(column, current_date, day_start, day_end, user_tz, day_data):
    """Execute a column's SQL query for a single day and populate day_data."""
    col_name = column.column_name
    try:
        with connection.cursor() as cursor:
            query, params = _prepare_sql_params(column.sql_query, current_date, day_start, day_end)
            cursor.execute(query, params)
            result = cursor.fetchone()
            count = result[0] if result and result[0] is not None else 0
            has_data = count > 0 and not _is_eat_clean_hidden(col_name, current_date, user_tz)

            day_data[f'has_{col_name}'] = has_data
            day_data[f'details_{col_name}'] = (
                _build_column_details(column, day_start, day_end, current_date, user_tz)
                if has_data and column.details_display
                else ''
            )

    except Exception as e:
        day_data[f'has_{col_name}'] = False
        day_data[f'details_{col_name}'] = ''
        print(f"Error executing query for {col_name}: {e}")


def _build_week_days(start_date, columns, user_tz):
    """Build the list of day data dicts for each day in the week."""
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    days = []
    current_date = start_date

    for i in range(7):
        day_start = user_tz.localize(datetime.combine(current_date, datetime.min.time()))
        day_end = user_tz.localize(datetime.combine(current_date, datetime.max.time()))

        day_data = {
            'name': day_names[i],
            'date': current_date,
            'date_str': current_date.strftime('%b %-d'),
            'date_iso': current_date.strftime('%Y-%m-%d'),
        }

        for column in columns:
            _query_column_for_day(column, current_date, day_start, day_end, user_tz, day_data)

        days.append(day_data)
        current_date += timedelta(days=1)

    return days


def _build_available_weeks(current_week_start, start_date):
    """Generate the list of available weeks from launch week to current week."""
    launch_week_start = date(2025, 11, 10)  # Monday, Nov 10, 2025
    weeks_diff = (current_week_start - launch_week_start).days // 7

    available_weeks = []
    for i in range(weeks_diff + 1):
        week_start = launch_week_start + timedelta(weeks=i)
        week_num = week_start.isocalendar()[1]
        available_weeks.append({
            'start_date': week_start.strftime('%Y-%m-%d'),
            'label': f"{week_start.strftime('%Y-%b-%d')} (Week {week_num})",
            'selected': week_start == start_date
        })

    available_weeks.reverse()
    return available_weeks


def life_tracker(request):
    """View for the weekly life tracker page."""
    import json

    user_tz = get_user_timezone(request)
    start_date, end_date, current_week_start = _parse_tracker_week_range(request)
    columns = _get_active_columns_for_week(start_date)
    days = _build_week_days(start_date, columns, user_tz)
    available_weeks = _build_available_weeks(current_week_start, start_date)

    columns_json = json.dumps([{
        'column_name': col.column_name,
        'display_name': col.display_name,
        'has_add_button': col.has_add_button,
        'modal_type': col.modal_type,
        'modal_title': col.modal_title,
        'modal_body_text': col.modal_body_text,
        'modal_input_label': col.modal_input_label,
        'create_endpoint': col.create_endpoint,
        'allow_abandon': col.allow_abandon,
        'abandoned_status': col.abandoned_status or {},
    } for col in columns])

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'days': days,
        'columns': columns,
        'columns_json': columns_json,
        'available_weeks': available_weeks,
    }

    return render(request, 'targets/life_tracker.html', context)


def _quote_reserved_keywords(sql_text):
    """Quote SQL reserved keywords (start, end, date) when used as column names."""
    import re
    for keyword in ['start', 'end', 'date']:
        pattern = r'(?<!["\w])(' + keyword + r')(?!["\w])'
        sql_text = re.sub(pattern, r'"\1"', sql_text, flags=re.IGNORECASE)
    return sql_text


def _convert_sqlite_to_postgres(sql_text):
    """Convert SQLite-specific functions (julianday) to PostgreSQL equivalents."""
    import re
    if connection.vendor != 'postgresql':
        return sql_text

    # julianday difference in minutes: (julianday(a) - julianday(b)) * 24 * 60
    pattern1 = r'\(julianday\(([^)]+)\)\s*-\s*julianday\(([^)]+)\)\)\s*\*\s*24\s*\*\s*60'
    sql_text = re.sub(pattern1, r'EXTRACT(EPOCH FROM (\1 - \2)) / 60', sql_text, flags=re.IGNORECASE)

    # julianday difference in days: (julianday(a) - julianday(b))
    pattern2 = r'\(julianday\(([^)]+)\)\s*-\s*julianday\(([^)]+)\)\)'
    sql_text = re.sub(pattern2, r'EXTRACT(EPOCH FROM (\1 - \2)) / 86400', sql_text, flags=re.IGNORECASE)

    # Single julianday(col) to epoch days
    pattern3 = r'julianday\(([^)]+)\)'
    sql_text = re.sub(pattern3, r'EXTRACT(EPOCH FROM \1) / 86400', sql_text, flags=re.IGNORECASE)

    return sql_text


def _format_entry_datetime(dt_value, timezone_str):
    """Convert a datetime or date value to a user-friendly localized string."""
    from django.utils import timezone as django_tz

    if not dt_value:
        return ''

    if isinstance(dt_value, date) and not isinstance(dt_value, datetime):
        return dt_value.strftime('%a, %-m/%-d/%y')

    if isinstance(dt_value, str):
        try:
            dt_value = datetime.fromisoformat(str(dt_value).replace('Z', '+00:00'))
        except Exception:
            return str(dt_value)

    if not hasattr(dt_value, 'tzinfo') or dt_value.tzinfo is None:
        dt_value = django_tz.make_aware(dt_value, pytz.UTC)

    try:
        user_tz = pytz.timezone(timezone_str)
        dt_local = dt_value.astimezone(user_tz)
        return dt_local.strftime('%a, %-m/%-d/%y @ %-I:%M %p')
    except Exception:
        return dt_value.strftime('%a, %-m/%-d/%y @ %-I:%M %p')


# Table name -> (display_col, sql_col) for date/sort columns in objective entries
_OBJECTIVE_TABLE_DATE_COLS = {
    'fasting_session': ('fast_end_date', 'fast_end_date'),
    'nutrition_entry': ('consumption_date', 'consumption_date'),
    'weight_weighin': ('measurement_time', 'measurement_time'),
    'workouts_workout': ('start', '"start"'),
    'targets_dailyagenda': ('date', '"date"'),
    'time_logs_timelog': ('start', '"start"'),
}


def _build_objective_id_query(sql, table_name, date_col_sql, objective):
    """Build the SQL query to fetch IDs for objective entry rows."""
    import re

    pk_column = 'id'
    where_match = re.search(r'\bWHERE\b((?:(?!\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b).)+)', sql, re.IGNORECASE | re.DOTALL)

    if where_match:
        where_clause = where_match.group(1).strip()
        where_clause = _quote_reserved_keywords(where_clause)
        where_clause = _convert_sqlite_to_postgres(where_clause)
        return f"SELECT {pk_column}, {date_col_sql} FROM {table_name} WHERE {where_clause} ORDER BY {date_col_sql} DESC LIMIT 50"

    # No WHERE clause - filter by objective's month
    if table_name == 'targets_dailyagenda':
        date_range_filter = f"{date_col_sql} >= '{objective.start}' AND {date_col_sql} <= '{objective.end}'"
    else:
        date_range_filter = f"{date_col_sql}::date >= '{objective.start}' AND {date_col_sql}::date <= '{objective.end}'"
    return f"SELECT {pk_column}, {date_col_sql} FROM {table_name} WHERE {date_range_filter} ORDER BY {date_col_sql} DESC LIMIT 50"


def _format_entry_with_custom_display(historical_display, row_dict, user_timezone):
    """Format a row using a custom historical_display template string."""
    entry_text = historical_display
    date_columns_to_check = ['start', 'end', 'date', 'fast_end_date', 'consumption_date', 'measurement_time', 'created_at']
    for date_col in date_columns_to_check:
        if f'{{{date_col}}}' in entry_text and date_col in row_dict:
            row_dict[date_col] = _format_entry_datetime(row_dict[date_col], user_timezone)

    try:
        return entry_text.format(**row_dict)
    except KeyError as e:
        return f"Format error: missing field {e}"
    except Exception as e:
        return f"Format error: {str(e)}"


def _format_entry_default(table_name, row_dict, user_timezone):
    """Format a row using default formatting based on the table type."""
    _fmt = _format_entry_datetime

    formatters = {
        'fasting_session': lambda r: f"{_fmt(r.get('fast_end_date', ''), user_timezone)}: {r.get('duration_hours', 0):.1f} hour fast",
        'nutrition_entry': lambda r: f"{_fmt(r.get('consumption_date', ''), user_timezone)}: {r.get('food_name', 'Food entry')}",
        'weight_weighin': lambda r: f"{_fmt(r.get('measurement_time', ''), user_timezone)}: {r.get('weight_kg', 0):.1f} kg",
        'workouts_workout': lambda r: f"{_fmt(r.get('start', ''), user_timezone)}: Sport {r.get('sport_id', 'Workout')} ({r.get('duration_minutes', 0)} min)",
        'time_logs_timelog': lambda r: f"{_fmt(r.get('start', ''), user_timezone)}: Project {r.get('project_id', 'Unknown')} ({r.get('duration_minutes', 0) / 60:.1f} hours)",
        'targets_dailyagenda': lambda r: f"{_fmt(r.get('date', ''), user_timezone)}: Agenda entry",
    }

    formatter = formatters.get(table_name)
    if formatter:
        return formatter(row_dict)

    # Fallback: show first 3 non-id columns
    display_cols = [k for k in row_dict.keys() if 'id' not in k.lower()][:3]
    return " | ".join(f"{k}: {row_dict[k]}" for k in display_cols)


def _make_objective_response(objective, entries):
    """Build a successful JSON response for objective entries."""
    return JsonResponse({
        'success': True,
        'objective_label': objective.label,
        'description': objective.description or '',
        'target': objective.objective_value,
        'current': objective.result or 0,
        'unit': objective.unit_of_measurement or '',
        'entries': entries,
        'count': len(entries)
    })


def _fetch_objective_detail_rows(table_name, id_rows, date_col_sql):
    """Fetch full row details for objective entries by their IDs."""
    ids_str = ','.join(str(row[0]) for row in id_rows)
    detail_query = f"SELECT * FROM {table_name} WHERE id IN ({ids_str}) ORDER BY {date_col_sql} DESC"

    with connection.cursor() as cursor:
        cursor.execute(detail_query)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _format_objective_entries(row_dicts, objective, table_name, user_timezone):
    """Format a list of row dicts into display strings using the objective's display template."""
    formatter = (
        (lambda rd: _format_entry_with_custom_display(objective.historical_display, rd, user_timezone))
        if objective.historical_display
        else (lambda rd: _format_entry_default(table_name, rd, user_timezone))
    )
    return [formatter(rd) for rd in row_dicts]


def get_objective_entries(request):
    """
    API endpoint to fetch the last entries contributing to a monthly objective.
    Returns JSON with either entries or an error message.
    """
    import re
    from monthly_objectives.models import MonthlyObjective

    objective_id = request.GET.get('objective_id')
    user_timezone = request.GET.get('timezone', 'UTC')

    if not objective_id:
        return JsonResponse({'error': 'objective_id is required'}, status=400)

    try:
        objective = MonthlyObjective.objects.get(objective_id=objective_id)
    except MonthlyObjective.DoesNotExist:
        return JsonResponse({'error': _OBJECTIVE_NOT_FOUND}, status=404)

    try:
        sql = objective.objective_definition.strip()

        if re.match(r'\s*WITH\s+', sql, re.IGNORECASE):
            return JsonResponse({
                'error': 'This objective uses a complex query (CTE) that cannot be displayed in detail view.',
                'objective_label': objective.label
            })

        from_match = re.search(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
        if not from_match:
            return JsonResponse({
                'error': 'Could not identify data source table.',
                'objective_label': objective.label
            })

        table_name = from_match.group(1)
        _date_col_display, date_col_sql = _OBJECTIVE_TABLE_DATE_COLS.get(table_name, ('created_at', 'created_at'))
        id_query = _build_objective_id_query(sql, table_name, date_col_sql, objective)

        with connection.cursor() as cursor:
            cursor.execute(id_query)
            id_rows = cursor.fetchall()

        if not id_rows:
            return _make_objective_response(objective, [])

        row_dicts = _fetch_objective_detail_rows(table_name, id_rows, date_col_sql)
        entries = _format_objective_entries(row_dicts, objective, table_name, user_timezone)

        return _make_objective_response(objective, entries)

    except Exception as e:
        import traceback
        return JsonResponse({
            'error': f'Error fetching entries: {str(e)}',
            'objective_label': objective.label,
            'traceback': traceback.format_exc()
        }, status=500)


def get_objective_available_fields(request):
    """
    API endpoint to get available database fields for historical_display formatting.
    Takes an SQL definition and returns the table's column names.
    """
    import re
    from django.db import connection

    sql_definition = request.GET.get('sql_definition', '').strip()

    if not sql_definition:
        return JsonResponse({'error': 'sql_definition parameter is required'}, status=400)

    try:
        # Extract table name from SQL definition
        from_match = re.search(r'\bFROM\s+(\w+)', sql_definition, re.IGNORECASE)
        if not from_match:
            return JsonResponse({
                'error': 'Could not identify table from SQL definition',
                'fields': []
            })

        table_name = from_match.group(1)

        # Query the database to get column names for this table
        with connection.cursor() as cursor:
            # Get column names by querying information_schema or using a LIMIT 0 query
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 0")
            columns = [col[0] for col in cursor.description]

        return JsonResponse({
            'success': True,
            'table_name': table_name,
            'fields': columns
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Error fetching fields: {str(e)}',
            'fields': []
        }, status=500)


def _extract_objective_fields(data):
    """Extract and return objective fields from request data dict."""
    return {
        'label': data.get('label', '').strip(),
        'month': data.get('month', ''),
        'year': data.get('year', ''),
        'objective_value': data.get('objective_value', ''),
        'objective_definition': data.get('objective_definition', '').strip(),
        'category': data.get('category', '').strip() or None,
        'description': data.get('description', '').strip() or None,
        'unit_of_measurement': data.get('unit_of_measurement', '').strip() or None,
        'historical_display': data.get('historical_display', '').strip() or None,
    }


_OBJECTIVE_REQUIRED_FIELDS_ERROR = (
    'All required fields must be filled: Label, Month, Year, Target Value, '
    'SQL Definition, Category, Description, and Unit of Measurement'
)


def _validate_objective_fields(fields):
    """
    Validate and parse objective fields. Returns (parsed_fields, error_response).
    error_response is a JsonResponse if validation fails, or None on success.
    parsed_fields includes parsed month, year, objective_value.
    """
    from calendar import monthrange
    from settings.models import Setting

    f = fields
    required = [f['label'], f['month'], f['year'], f['objective_value'],
                f['objective_definition'], f['category'], f['description'], f['unit_of_measurement']]
    if not all(required):
        return None, JsonResponse({'error': _OBJECTIVE_REQUIRED_FIELDS_ERROR}, status=400)

    try:
        month = int(f['month'])
        year = int(f['year'])
        if not (1 <= month <= 12):
            raise ValueError("Month must be between 1 and 12")
        if not (2020 <= year <= 2050):
            raise ValueError("Year must be between 2020 and 2050")
    except (ValueError, TypeError) as e:
        return None, JsonResponse({'error': f'Invalid month or year: {str(e)}'}, status=400)

    try:
        objective_value = float(f['objective_value'])
    except (ValueError, TypeError):
        return None, JsonResponse({'error': 'Invalid objective value - must be a number'}, status=400)

    if objective_value < 0:
        return None, JsonResponse({'error': 'Objective value must be greater than or equal to zero'}, status=400)

    timezone_str = Setting.get('default_timezone_for_monthly_objectives', 'America/Chicago')
    start_date = datetime(year, month, 1).date()
    last_day = monthrange(year, month)[1]
    end_date = datetime(year, month, last_day).date()

    parsed = dict(f)
    parsed.update({
        'month': month,
        'year': year,
        'objective_value': objective_value,
        'timezone_str': timezone_str,
        'start_date': start_date,
        'end_date': end_date,
    })
    return parsed, None


def _execute_objective_sql(sql_definition):
    """Execute an objective's SQL and return the numeric result, or 0 on failure."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql_definition)
            row = cursor.fetchone()
            return float(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def _compute_objective_derived_values(result, objective_value, month, year):
    """Compute progress_pct, achieved, and target_per_week for an objective."""
    from calendar import monthrange

    progress_pct = round((result / objective_value) * 100, 1) if result is not None and objective_value > 0 else 0
    achieved = result is not None and result >= objective_value

    days_in_month = monthrange(year, month)[1]
    weeks_in_month = days_in_month / 7.0
    target_per_week = round(objective_value / weeks_in_month, 1) if weeks_in_month > 0 else 0

    return progress_pct, achieved, target_per_week


@require_http_methods(["POST"])
def create_objective(request):
    """API endpoint to create a new monthly objective."""
    import json
    import re
    from monthly_objectives.models import MonthlyObjective

    try:
        data = json.loads(request.body)
        fields = _extract_objective_fields(data)
        parsed, err = _validate_objective_fields(fields)
        if err:
            return err

        # Generate objective_id from label, month, and year
        label_slug = re.sub(r'[^\w\s-]', '', parsed['label'].lower())
        label_slug = re.sub(r'[-\s]+', '_', label_slug).strip('_')
        month_abbrev = datetime(parsed['year'], parsed['month'], 1).strftime('%b').lower()
        objective_id = f"{label_slug}_{month_abbrev}_{parsed['year']}"

        if MonthlyObjective.objects.filter(objective_id=objective_id).exists():
            return JsonResponse({
                'error': f'An objective with this label already exists for {month_abbrev.capitalize()} {parsed["year"]}. Please use a different label.'
            }, status=400)

        objective = MonthlyObjective.objects.create(
            objective_id=objective_id,
            label=parsed['label'],
            start=parsed['start_date'],
            end=parsed['end_date'],
            timezone=parsed['timezone_str'],
            objective_value=parsed['objective_value'],
            objective_definition=parsed['objective_definition'],
            category=parsed['category'],
            description=parsed['description'],
            unit_of_measurement=parsed['unit_of_measurement'],
            historical_display=parsed['historical_display'],
            result=None
        )

        objective.result = _execute_objective_sql(objective.objective_definition)
        objective.save()

        progress_pct, achieved, target_per_week = _compute_objective_derived_values(
            objective.result, objective.objective_value, parsed['month'], parsed['year']
        )

        return JsonResponse({
            'success': True,
            'message': f'Objective "{parsed["label"]}" created successfully!',
            'objective_id': objective.objective_id,
            'in_current_range': True,
            'objective': {
                'objective_id': objective.objective_id,
                'label': objective.label,
                'category': objective.category,
                'description': objective.description,
                'unit': objective.unit_of_measurement,
                'historical_display': objective.historical_display,
                'target': objective.objective_value,
                'result': objective.result,
                'progress_pct': progress_pct,
                'achieved': achieved,
                'target_per_week': target_per_week,
                'month': parsed['month'],
                'year': parsed['year'],
                'objective_value': objective.objective_value,
                'objective_definition': objective.objective_definition,
                'start': objective.start.isoformat(),
                'end': objective.end.isoformat(),
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': _INVALID_JSON}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error creating objective: {str(e)}'}, status=500)


@require_http_methods(["POST"])
def update_objective(request):
    """API endpoint to update an existing monthly objective."""
    import json
    import logging
    from monthly_objectives.models import MonthlyObjective

    logger = logging.getLogger(__name__)

    try:
        data = json.loads(request.body)
        logger.info("=== UPDATE OBJECTIVE REQUEST ===")
        logger.info(f"Received data keys: {data.keys()}")
        logger.info(f"historical_display in request: {data.get('historical_display')}")

        objective_id = data.get('objective_id', '').strip()
        fields = _extract_objective_fields(data)

        # objective_id is additionally required for updates
        required_with_id = [objective_id] + [fields[k] for k in ['label', 'month', 'year', 'objective_value',
                                                                   'objective_definition', 'category', 'description', 'unit_of_measurement']]
        if not all(required_with_id):
            logger.error("Validation failed - missing required fields")
            return JsonResponse({'error': _OBJECTIVE_REQUIRED_FIELDS_ERROR}, status=400)

        try:
            objective = MonthlyObjective.objects.get(objective_id=objective_id)
        except MonthlyObjective.DoesNotExist:
            return JsonResponse({'error': _OBJECTIVE_NOT_FOUND}, status=404)

        parsed, err = _validate_objective_fields(fields)
        if err:
            return err

        logger.info(f"BEFORE UPDATE - objective.historical_display: {repr(objective.historical_display)}")
        objective.label = parsed['label']
        objective.start = parsed['start_date']
        objective.end = parsed['end_date']
        objective.timezone = parsed['timezone_str']
        objective.objective_value = parsed['objective_value']
        objective.objective_definition = parsed['objective_definition']
        objective.category = parsed['category']
        objective.description = parsed['description']
        objective.unit_of_measurement = parsed['unit_of_measurement']
        objective.historical_display = parsed['historical_display']
        logger.info(f"AFTER ASSIGNMENT - objective.historical_display: {repr(objective.historical_display)}")
        objective.save()
        logger.info(f"AFTER SAVE - objective.historical_display: {repr(objective.historical_display)}")

        objective.refresh_from_db()
        logger.info(f"AFTER REFRESH - objective.historical_display: {repr(objective.historical_display)}")

        result = _execute_objective_sql(parsed['objective_definition'])
        progress_pct, achieved, target_per_week = _compute_objective_derived_values(
            result, parsed['objective_value'], parsed['month'], parsed['year']
        )

        return JsonResponse({
            'success': True,
            'message': f'Objective "{parsed["label"]}" updated successfully!',
            'objective_id': objective.objective_id,
            'in_current_range': False,
            'objective': {
                'label': parsed['label'],
                'target': parsed['objective_value'],
                'result': result if result is not None else 0,
                'progress_pct': progress_pct,
                'achieved': achieved,
                'month': parsed['month'],
                'year': parsed['year'],
                'objective_value': parsed['objective_value'],
                'objective_definition': parsed['objective_definition'],
                'category': parsed['category'],
                'description': parsed['description'],
                'unit': parsed['unit_of_measurement'],
                'historical_display': parsed['historical_display'],
                'target_per_week': target_per_week
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': _INVALID_JSON}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error updating objective: {str(e)}'}, status=500)


def delete_objective(request):
    """API endpoint to delete a monthly objective."""
    import json
    from monthly_objectives.models import MonthlyObjective

    try:
        # Parse JSON data
        data = json.loads(request.body)

        # Extract objective_id
        objective_id = data.get('objective_id', '').strip()

        # Validate required field
        if not objective_id:
            return JsonResponse({
                'error': 'Objective ID is required'
            }, status=400)

        # Get the existing objective
        try:
            objective = MonthlyObjective.objects.get(objective_id=objective_id)
            objective_label = objective.label
            objective.delete()
        except MonthlyObjective.DoesNotExist:
            return JsonResponse({
                'error': _OBJECTIVE_NOT_FOUND
            }, status=404)

        return JsonResponse({
            'success': True,
            'message': f'Objective "{objective_label}" deleted successfully!'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'error': _INVALID_JSON
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Error deleting objective: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
def refresh_objective_cache(request):
    """Refresh cached results for all monthly objectives"""
    from monthly_objectives.models import MonthlyObjective

    # Check authentication (return JSON error instead of redirect for AJAX)
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'error': 'Authentication required'
        }, status=401)

    try:
        objectives = MonthlyObjective.objects.all()
        updated_count = 0
        error_count = 0
        errors = []

        for obj in objectives:
            try:
                # Execute the SQL query
                with connection.cursor() as cursor:
                    cursor.execute(obj.objective_definition)
                    row = cursor.fetchone()

                    if row and row[0] is not None:
                        result = float(row[0])
                    else:
                        result = 0.0

                # Update the result field
                obj.result = result
                obj.save(update_fields=['result'])
                updated_count += 1

            except Exception as e:
                error_count += 1
                errors.append(f'{obj.label}: {str(e)}')

        return JsonResponse({
            'success': True,
            'updated_count': updated_count,
            'error_count': error_count,
            'errors': errors if errors else None,
            'message': f'Refreshed {updated_count} objective(s)' + (f', {error_count} error(s)' if error_count > 0 else '')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
