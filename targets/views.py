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
    # Use timezone-aware date to handle different timezones correctly
    today = timezone.now().date()

    if request.method == 'POST':
        # Get or create today's agenda
        agenda, created = DailyAgenda.objects.get_or_create(date=today)

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
def sync_toggl_projects_goals(request):
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


@require_http_methods(["POST"])
def save_agenda(request):
    """AJAX endpoint to save agenda for a specific date (or today if not specified)."""
    try:
        # Check if a specific date was provided (for editing past agendas)
        date_str = request.POST.get('date')

        if date_str:
            # Parse the provided date
            from datetime import datetime
            agenda_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            # Use UTC date to ensure consistency across timezones
            # This ensures the same UTC day is used regardless of user's location
            agenda_date = timezone.now().date()  # timezone.now() returns current UTC time

        # Get or create agenda for the specified date
        agenda, created = DailyAgenda.objects.get_or_create(date=agenda_date)

        # Process each target
        for i in range(1, 4):
            project_id = request.POST.get(f'project_{i}')
            goal_id = request.POST.get(f'goal_{i}')
            target_input = request.POST.get(f'target_{i}')

            # Save if we have project and target (goal is optional)
            if project_id and target_input:
                # Set agenda fields directly with text
                setattr(agenda, f'project_{i}_id', project_id)
                setattr(agenda, f'goal_{i}_id', goal_id if goal_id else None)
                setattr(agenda, f'target_{i}', target_input)
            else:
                # Clear fields if not provided
                setattr(agenda, f'project_{i}_id', None)
                setattr(agenda, f'goal_{i}_id', None)
                setattr(agenda, f'target_{i}', None)
                # Also clear the score if target is removed
                setattr(agenda, f'target_{i}_score', None)

        # Save other plans if provided
        other_plans = request.POST.get('other_plans', '')
        agenda.other_plans = other_plans

        # If other_plans is being cleared, also clear its score
        if not other_plans:
            agenda.other_plans_score = None

        # Calculate and save overall day score
        # Count how many targets/plans are set
        targets_set = 0
        total_score = 0

        # Check targets 1-3
        for i in range(1, 4):
            target = getattr(agenda, f'target_{i}')
            target_score = getattr(agenda, f'target_{i}_score')

            # Target is set if it exists
            if target:
                targets_set += 1
                # Add score if it exists (0, 0.5, or 1)
                if target_score is not None:
                    total_score += target_score

        # Check other_plans
        if agenda.other_plans:
            targets_set += 1
            # Add score if it exists (0, 0.5, or 1)
            if agenda.other_plans_score is not None:
                total_score += agenda.other_plans_score

        # Calculate day score if any targets/plans are set
        if targets_set > 0:
            agenda.day_score = total_score / targets_set
        else:
            agenda.day_score = None

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


def get_toggl_time_today(request):
    """
    AJAX endpoint to get time spent on a project (and optionally a goal/tag).
    - For today: pulls from Toggl API (includes running timers)
    - For past dates: pulls from database (historical data)
    """
    try:
        project_id = request.GET.get('project_id')
        goal_id = request.GET.get('goal_id')  # This is the tag ID from the goals table
        timezone_offset = request.GET.get('timezone_offset')  # User's timezone offset in minutes
        date_str = request.GET.get('date')  # Optional: specific date to query (YYYY-MM-DD)

        if not project_id:
            return JsonResponse({'error': 'project_id is required'}, status=400)

        # Convert goal_id (tag ID) to tag name for Toggl API comparison
        # The Toggl API returns tag names, not tag IDs
        goal_tag_name = None
        if goal_id:
            from goals.models import Goal
            try:
                goal = Goal.objects.get(goal_id=goal_id)
                goal_tag_name = goal.display_string
            except Goal.DoesNotExist:
                # If goal not found, skip tag filtering
                pass

        # Determine the target date
        now = timezone.now()

        if date_str:
            # Parse the provided date
            from datetime import datetime as dt
            target_date = dt.strptime(date_str, '%Y-%m-%d').date()
            today_date = now.date()
            is_today = (target_date == today_date)
        else:
            # No date provided, use today
            target_date = now.date()
            is_today = True

        # If it's today, query Toggl API for real-time data
        if is_today:
            from time_logs.services.toggl_client import TogglAPIClient
            from django.core.cache import cache

            # Calculate today_start for cache key and API call
            if timezone_offset:
                # timezone_offset is in minutes (e.g., 480 for PST which is UTC-8)
                # JavaScript's getTimezoneOffset() returns positive for west of UTC
                offset_minutes = int(timezone_offset)
                offset_delta = timedelta(minutes=-offset_minutes)  # Negate because JS uses opposite sign

                # Calculate start of today in user's local timezone
                local_now = now + offset_delta
                local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_start = local_midnight - offset_delta  # Convert back to UTC
            else:
                # Fallback to UTC
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Create cache key based on date and 5-minute interval to reduce API calls
            # This groups all requests within the same 5-minute window to share cache
            five_min_interval = now.minute // 5
            cache_key = f"toggl_entries_{today_start.date()}_{now.hour}_{five_min_interval}"

            # Try to get from cache first (5 minute cache to avoid hitting 30 req/hour limit)
            time_entries = cache.get(cache_key)

            if time_entries is None:
                # Not in cache, fetch from Toggl API
                try:
                    client = TogglAPIClient()
                    time_entries = client.get_time_entries(
                        start_date=today_start,
                        end_date=now
                    )
                    # Cache for 5 minutes (300 seconds)
                    # This helps avoid Toggl's 30 req/hour limit on /me endpoints
                    cache.set(cache_key, time_entries, 300)
                except Exception as api_error:
                    # Check if it's a rate limit error (402 or 429)
                    error_str = str(api_error)
                    if '402' in error_str or '429' in error_str or 'rate' in error_str.lower():
                        # Return cached data if available (even if expired)
                        time_entries = cache.get(cache_key, [])
                        if not time_entries:
                            # No cache, return friendly error
                            raise Exception("Toggl API rate limit reached. Please wait a moment and refresh.")
                    else:
                        raise  # Re-raise non-rate-limit errors

            # Filter entries by project_id and optionally goal_id (tag)
            total_seconds = 0
            matched_entries = []  # For debugging

            for entry in time_entries:
                entry_project_id = entry.get('project_id')
                entry_tags = entry.get('tags', [])
                entry_duration = entry.get('duration', 0)  # Duration in seconds (negative if running)
                entry_start = entry.get('start')

                # Check if this entry matches the project
                if str(entry_project_id) != str(project_id):
                    continue

                # If goal_id is specified, check if entry has this tag (by tag name)
                if goal_tag_name and goal_tag_name not in entry_tags:
                    continue

                # If duration is negative, it's a running timer
                # Calculate actual duration from start time to now
                is_running = entry_duration < 0
                if is_running and entry_start:
                    start_dt = datetime.fromisoformat(entry_start.replace('Z', '+00:00'))
                    entry_duration = int((now - start_dt).total_seconds())

                total_seconds += entry_duration

                # Debug info
                matched_entries.append({
                    'start': entry_start,
                    'duration_seconds': entry_duration,
                    'is_running': is_running,
                    'tags': entry_tags
                })

            debug_info = {
                'query_start': today_start.isoformat(),
                'query_end': now.isoformat(),
                'timezone_offset': timezone_offset if timezone_offset else 'UTC (not provided)',
                'source': 'toggl_api',
                'entries_count': len(matched_entries),
                'entries': matched_entries
            }

        else:
            # Past date - query database
            from time_logs.models import TimeLog
            from datetime import datetime as dt

            # Calculate start and end of the target date in UTC
            # Use timezone offset to determine the user's local day boundaries
            if timezone_offset:
                offset_minutes = int(timezone_offset)
                offset_delta = timedelta(minutes=-offset_minutes)

                # Convert target date to user's local timezone
                target_datetime = dt.combine(target_date, dt.min.time())
                target_datetime_utc = timezone.make_aware(target_datetime)

                # Calculate local midnight
                local_midnight = target_datetime_utc + offset_delta
                next_local_midnight = local_midnight + timedelta(days=1)

                # Convert back to UTC for database query
                day_start_utc = local_midnight - offset_delta
                day_end_utc = next_local_midnight - offset_delta
            else:
                # Fallback to UTC
                day_start_utc = timezone.make_aware(dt.combine(target_date, dt.min.time()))
                day_end_utc = day_start_utc + timedelta(days=1)

            # Query time logs for this date and project
            time_logs = TimeLog.objects.filter(
                project_id=int(project_id),
                start__gte=day_start_utc,
                start__lt=day_end_utc
            )

            # If goal_id is specified, filter by goal
            if goal_id:
                time_logs = time_logs.filter(goals__goal_id=goal_id).distinct()

            # Calculate total duration
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
                'timezone_offset': timezone_offset if timezone_offset else 'UTC (not provided)',
                'source': 'database',
                'target_date': target_date.isoformat(),
                'entries_count': len(matched_entries),
                'entries': matched_entries
            }

        # Convert to hours and minutes
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)

        # Format the display string
        if hours > 0:
            time_display = f"{hours}h {minutes}m"
        else:
            time_display = f"{minutes}m"

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
        error_details = traceback.format_exc()
        print(f"Error in get_toggl_time_today: {error_details}")

        # Check if it's a Toggl API error
        error_msg = str(e)
        if '402' in error_msg or 'Payment Required' in error_msg:
            error_msg = "Toggl API payment required - please check your Toggl subscription"

        return JsonResponse({
            'success': False,
            'error': error_msg
        }, status=500)


def get_available_agenda_dates(request):
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
                'other_plans_score': agenda.other_plans_score,
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
        target_num = request.POST.get('target_num')
        score = request.POST.get('score')

        if not date_str or not target_num or score is None:
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters'
            }, status=400)

        # Validate target_num (1-3 for targets, 4 for other_plans)
        try:
            target_num = int(target_num)
            if target_num not in [1, 2, 3, 4]:
                raise ValueError()
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'target_num must be 1, 2, 3, or 4'
            }, status=400)

        # Validate score (allow "null" string to clear the score)
        if score == 'null':
            score = None
        else:
            try:
                score = float(score)
                if score not in [0, 0.5, 1]:
                    raise ValueError()
            except (ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'error': 'score must be 0, 0.5, 1, or null'
                }, status=400)

        # Parse the date
        from datetime import datetime as dt
        agenda_date = dt.strptime(date_str, '%Y-%m-%d').date()

        # Get the agenda for this date
        try:
            agenda = DailyAgenda.objects.get(date=agenda_date)
        except DailyAgenda.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'No agenda found for this date'
            }, status=404)

        # Set the score for the specified target (or other_plans if target_num is 4)
        if target_num == 4:
            agenda.other_plans_score = score
        else:
            setattr(agenda, f'target_{target_num}_score', score)

        # Calculate and save overall day score
        # Count how many targets/plans are set
        targets_set = 0
        total_score = 0

        # Check targets 1-3
        for i in range(1, 4):
            target = getattr(agenda, f'target_{i}')
            target_score = getattr(agenda, f'target_{i}_score')

            # Target is set if it exists
            if target:
                targets_set += 1
                # Add score if it exists (0, 0.5, or 1)
                if target_score is not None:
                    total_score += target_score

        # Check other_plans
        if agenda.other_plans:
            targets_set += 1
            # Add score if it exists (0, 0.5, or 1)
            if agenda.other_plans_score is not None:
                total_score += agenda.other_plans_score

        # Calculate day score if any targets/plans are set
        if targets_set > 0:
            agenda.day_score = total_score / targets_set
        else:
            agenda.day_score = None

        agenda.save()

        return JsonResponse({
            'success': True,
            'message': f'Score saved for target {target_num}',
            'day_score': agenda.day_score
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def activity_report(request):
    """View for activity summary report across a date range."""
    from django.db.models import Sum, Avg, Count, Min, Max
    from fasting.models import FastingSession
    from nutrition.models import NutritionEntry
    from weight.models import WeighIn
    from workouts.models import Workout
    from external_data.models import WhoopSportId

    # Load sport ID to name mapping from database
    sport_names_dict = {sport.sport_id: sport.sport_name for sport in WhoopSportId.objects.all()}

    # Get date range from query params or default to current week
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        # Default to current week (Monday-Sunday)
        today = date.today()
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)

    # Convert to datetime for filtering
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    days_in_range = (end_date - start_date).days + 1

    # FASTING DATA
    fasting_sessions = FastingSession.objects.filter(
        fast_end_date__gte=start_datetime,
        fast_end_date__lte=end_datetime
    )
    # Count unique days with fasts
    from django.db.models.functions import TruncDate
    days_with_fasts = fasting_sessions.annotate(
        fast_date=TruncDate('fast_end_date')
    ).values('fast_date').distinct().count()

    # Get total fasts from all time
    year_fast_count = FastingSession.objects.count()

    fasting_stats = {
        'count': fasting_sessions.count(),
        'avg_duration': fasting_sessions.aggregate(Avg('duration'))['duration__avg'] or 0,
        'max_duration': fasting_sessions.aggregate(Max('duration'))['duration__max'] or 0,
        'total_hours': fasting_sessions.aggregate(Sum('duration'))['duration__sum'] or 0,
        'year_count': year_fast_count,
        'percent_days_fasted': round((days_with_fasts / days_in_range * 100), 1) if days_in_range > 0 else 0,
    }

    # NUTRITION DATA
    nutrition_entries = NutritionEntry.objects.filter(
        consumption_date__gte=start_datetime,
        consumption_date__lte=end_datetime
    )

    # Count unique days with nutrition data
    days_tracked = nutrition_entries.values('consumption_date__date').distinct().count()
    percent_tracked = round((days_tracked / days_in_range * 100), 1) if days_in_range > 0 else 0

    nutrition_agg = nutrition_entries.aggregate(
        total_calories=Sum('calories'),
        total_protein=Sum('protein'),
        total_carbs=Sum('carbs'),
        total_fat=Sum('fat'),
    )

    # Calculate averages per day tracked (not per day in range)
    nutrition_stats = {
        'days_tracked': days_tracked,
        'days_in_range': days_in_range,
        'percent_tracked': percent_tracked,
        'avg_calories': float(nutrition_agg['total_calories'] or 0) / days_tracked if days_tracked > 0 else 0,
        'avg_protein': float(nutrition_agg['total_protein'] or 0) / days_tracked if days_tracked > 0 else 0,
        'avg_carbs': float(nutrition_agg['total_carbs'] or 0) / days_tracked if days_tracked > 0 else 0,
        'avg_fat': float(nutrition_agg['total_fat'] or 0) / days_tracked if days_tracked > 0 else 0,
    }

    # WEIGHT DATA
    weigh_ins = WeighIn.objects.filter(
        measurement_time__gte=start_datetime,
        measurement_time__lte=end_datetime
    ).order_by('measurement_time')

    weight_stats = {
        'count': weigh_ins.count(),
        'start_weight': None,
        'end_weight': None,
        'change': None,
        'avg_weight': None,
        'year_change': None
    }

    if weigh_ins.exists():
        weight_stats['start_weight'] = float(weigh_ins.first().weight)
        weight_stats['end_weight'] = float(weigh_ins.last().weight)
        weight_stats['change'] = weight_stats['end_weight'] - weight_stats['start_weight']
        weight_stats['avg_weight'] = float(weigh_ins.aggregate(Avg('weight'))['weight__avg'])

        # Calculate change from earliest weight in database to current
        earliest_weigh_in = WeighIn.objects.order_by('measurement_time').first()
        if earliest_weigh_in:
            earliest_weight = float(earliest_weigh_in.weight)
            weight_stats['year_change'] = weight_stats['end_weight'] - earliest_weight

    # WORKOUT DATA - Group by sport_id
    workouts = Workout.objects.filter(
        start__gte=start_datetime,
        start__lte=end_datetime
    )

    workouts_by_sport = {}
    for workout in workouts:
        sport_id = workout.sport_id
        sport_name = sport_names_dict.get(sport_id, f'Sport {sport_id}')

        if sport_name not in workouts_by_sport:
            workouts_by_sport[sport_name] = {
                'count': 0,
                'total_calories': 0,
                'total_seconds': 0,
                'total_hours': 0,
                'avg_heart_rate': []
            }

        workouts_by_sport[sport_name]['count'] += 1
        if workout.calories_burned:
            workouts_by_sport[sport_name]['total_calories'] += float(workout.calories_burned)
        if workout.end:
            duration = (workout.end - workout.start).total_seconds()
            workouts_by_sport[sport_name]['total_seconds'] += duration
        if workout.average_heart_rate:
            workouts_by_sport[sport_name]['avg_heart_rate'].append(workout.average_heart_rate)

    # Calculate averages and format for each sport
    for sport_name in workouts_by_sport:
        sport_data = workouts_by_sport[sport_name]
        sport_data['total_hours'] = round(sport_data['total_seconds'] / 3600, 1)
        if sport_data['avg_heart_rate']:
            sport_data['avg_heart_rate'] = round(sum(sport_data['avg_heart_rate']) / len(sport_data['avg_heart_rate']))
        else:
            sport_data['avg_heart_rate'] = 0
        del sport_data['total_seconds']  # Remove intermediate value

    # Sort by workout count (descending)
    workouts_by_sport = dict(sorted(
        workouts_by_sport.items(),
        key=lambda x: x[1]['count'],
        reverse=True
    ))

    # TIME LOGS DATA - Group by project and goal
    time_logs = TimeLog.objects.filter(
        start__gte=start_datetime,
        start__lte=end_datetime
    ).prefetch_related('goals')

    time_by_project = {}

    for log in time_logs:
        try:
            project = Project.objects.get(project_id=log.project_id)
            project_name = project.display_string
        except Project.DoesNotExist:
            project_name = f"Project {log.project_id}"

        duration_hours = (log.end - log.start).total_seconds() / 3600

        if project_name not in time_by_project:
            time_by_project[project_name] = {
                'total_hours': 0,
                'goals': {}
            }

        time_by_project[project_name]['total_hours'] += duration_hours

        # Add goal breakdown
        for goal in log.goals.all():
            goal_name = goal.display_string
            if goal_name not in time_by_project[project_name]['goals']:
                time_by_project[project_name]['goals'][goal_name] = 0
            time_by_project[project_name]['goals'][goal_name] += duration_hours

    # Sort projects by hours (descending)
    time_by_project = dict(sorted(
        time_by_project.items(),
        key=lambda x: x[1]['total_hours'],
        reverse=True
    ))

    # Sort goals within each project
    for project_name in time_by_project:
        time_by_project[project_name]['goals'] = dict(sorted(
            time_by_project[project_name]['goals'].items(),
            key=lambda x: x[1],
            reverse=True
        ))

    # Calculate total hours across all projects
    total_time_hours = sum(project_data['total_hours'] for project_data in time_by_project.values())

    # Add percentage for each project and goal
    for project_name, project_data in time_by_project.items():
        # Calculate project percentage
        if total_time_hours > 0:
            project_data['percentage'] = round((project_data['total_hours'] / total_time_hours) * 100)
        else:
            project_data['percentage'] = 0

        # Calculate goal percentages
        project_total = project_data['total_hours']
        for goal_name in project_data['goals']:
            if project_total > 0:
                goal_hours = project_data['goals'][goal_name]
                project_data['goals'][goal_name] = {
                    'hours': goal_hours,
                    'percentage': round((goal_hours / total_time_hours) * 100)
                }
            else:
                project_data['goals'][goal_name] = {
                    'hours': project_data['goals'][goal_name],
                    'percentage': 0
                }

    # MONTHLY OBJECTIVES
    from monthly_objectives.models import MonthlyObjective
    from calendar import monthrange

    # Check if date range crosses month boundaries
    crosses_months = (start_date.year != end_date.year) or (start_date.month != end_date.month)

    # Use end_date's month for objectives
    target_month_first_day = end_date.replace(day=1)
    last_day = monthrange(end_date.year, end_date.month)[1]
    target_month_last_day = end_date.replace(day=last_day)

    # Query objectives for the target month
    monthly_objectives = MonthlyObjective.objects.filter(
        start=target_month_first_day,
        end=target_month_last_day
    ).order_by('label')

    # Update objective results before displaying
    for obj in monthly_objectives:
        try:
            with connection.cursor() as cursor:
                cursor.execute(obj.objective_definition)
                row = cursor.fetchone()

                if row and row[0] is not None:
                    result = float(row[0])
                else:
                    result = 0.0

                # Update the result field in database
                obj.result = result
                obj.save(update_fields=['result'])
        except Exception:
            # If SQL fails, keep existing result or set to 0
            if obj.result is None:
                obj.result = 0.0
                obj.save(update_fields=['result'])

    # Format objectives data for template
    objectives_data = []
    for obj in monthly_objectives:
        # Use cached result from database
        result = obj.result if obj.result is not None else 0

        # Calculate progress
        progress_pct = 0
        if result is not None and obj.objective_value > 0:
            progress_pct = (result / obj.objective_value) * 100

        # Calculate target per week
        days_in_month = monthrange(obj.start.year, obj.start.month)[1]
        weeks_in_month = days_in_month / 7.0
        target_per_week = obj.objective_value / weeks_in_month if weeks_in_month > 0 else 0

        # Calculate remaining (0 if achieved or exceeded)
        remaining = max(0, obj.objective_value - (result if result is not None else 0))

        objectives_data.append({
            'objective_id': obj.objective_id,
            'label': obj.label,
            'description': obj.description,
            'start': obj.start,
            'target': obj.objective_value,
            'result': result if result is not None else 0,
            'progress_pct': round(progress_pct, 1),
            'achieved': result is not None and result >= obj.objective_value,
            'objective_value': obj.objective_value,
            'objective_definition': obj.objective_definition,
            'category': obj.category,
            'target_per_week': round(target_per_week, 1),
            'days_in_month': days_in_month,
            'remaining': round(remaining, 1),
            'unit': obj.unit_of_measurement,
        })

    # Group objectives by category
    from collections import defaultdict
    objectives_by_category = defaultdict(list)
    uncategorized = []

    for obj in objectives_data:
        if obj['category']:
            objectives_by_category[obj['category']].append(obj)
        else:
            uncategorized.append(obj)

    # Define category display config for predefined categories (icons and colors)
    category_config = {
        'Exercise': {'icon': 'bi-lightning-charge-fill', 'color': 'danger'},
        'Nutrition': {'icon': 'bi-egg-fried', 'color': 'success'},
        'Weight': {'icon': 'bi-speedometer2', 'color': 'info'},
        'Time Mgmt': {'icon': 'bi-clock-fill', 'color': 'warning'},
    }

    # Get all categories from the current month's objectives
    # Start with predefined categories in order, then add any custom categories alphabetically
    all_categories = []
    predefined_order = ['Exercise', 'Nutrition', 'Weight', 'Time Mgmt']

    # Add predefined categories first (if they have objectives)
    for cat in predefined_order:
        if cat in objectives_by_category and objectives_by_category[cat]:
            all_categories.append(cat)

    # Add any custom categories (not in predefined list) alphabetically
    custom_categories = sorted([cat for cat in objectives_by_category.keys() if cat not in predefined_order])
    all_categories.extend(custom_categories)

    monthly_objectives_context = {
        'objectives': objectives_data,
        'objectives_by_category': dict(objectives_by_category),
        'uncategorized': uncategorized,
        'category_config': category_config,
        'all_categories': all_categories,  # All categories with objectives (predefined + custom)
        'target_month': end_date.strftime('%b %Y').upper(),
        'crosses_months': crosses_months,
    }

    # TODAY'S ACTIVITY DATA
    # Get today's date and times based on the user's browser timezone
    today, today_start, today_end = get_user_today(request)
    user_tz = get_user_timezone(request)

    # Today's workouts
    todays_workouts = Workout.objects.filter(
        start__gte=today_start,
        start__lte=today_end
    ).order_by('-start')

    # Today's time logs with projects and goals
    todays_time_logs = TimeLog.objects.filter(
        start__gte=today_start,
        start__lte=today_end
    ).prefetch_related('goals').order_by('-start')

    # Serialize time logs for JSON (for pie chart)
    import json
    time_logs_json = []
    for log in todays_time_logs:
        try:
            project = Project.objects.get(project_id=log.project_id)
            project_name = project.display_string
        except Project.DoesNotExist:
            project_name = f"Project {log.project_id}"

        duration = (log.end - log.start).total_seconds() if log.end else 0
        time_logs_json.append({
            'project': project_name,
            'duration': duration
        })

    time_logs_json_str = json.dumps(time_logs_json)

    # Today's fasting sessions
    todays_fasts = FastingSession.objects.filter(
        fast_end_date__gte=today_start,
        fast_end_date__lte=today_end
    ).order_by('-fast_end_date')

    # Today's nutrition entries
    todays_nutrition = NutritionEntry.objects.filter(
        consumption_date__gte=today_start,
        consumption_date__lte=today_end
    ).order_by('-consumption_date')

    # Today's weigh-ins
    todays_weighins = WeighIn.objects.filter(
        measurement_time__gte=today_start,
        measurement_time__lte=today_end
    ).order_by('-measurement_time')

    todays_activity = {
        'workouts': todays_workouts,
        'time_logs': todays_time_logs,
        'time_logs_json': time_logs_json_str,
        'fasts': todays_fasts,
        'nutrition': todays_nutrition,
        'weighins': todays_weighins,
        'sport_names': sport_names_dict,
    }

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'days_in_range': days_in_range,
        'fasting': fasting_stats,
        'nutrition': nutrition_stats,
        'weight': weight_stats,
        'workouts_by_sport': workouts_by_sport,
        'time_by_project': time_by_project,
        'total_time_hours': round(total_time_hours, 1),
        'monthly_objectives': monthly_objectives_context,
        'todays_activity': todays_activity,
        'today': today,
        'user_timezone': user_tz,
    }

    return render(request, 'targets/activity_report.html', context)


@require_http_methods(["POST"])
def create_objective(request):
    """API endpoint to create a new monthly objective."""
    import json
    import re
    from calendar import monthrange
    from monthly_objectives.models import MonthlyObjective
    from settings.models import Setting

    try:
        # Parse JSON data
        data = json.loads(request.body)

        # Extract and validate fields
        label = data.get('label', '').strip()
        month = data.get('month', '')
        year = data.get('year', '')
        objective_value = data.get('objective_value', '')
        objective_definition = data.get('objective_definition', '').strip()
        category = data.get('category', '').strip() or None
        description = data.get('description', '').strip() or None
        unit_of_measurement = data.get('unit_of_measurement', '').strip() or None

        # Validate required fields
        if not all([label, month, year, objective_value, objective_definition, category, description, unit_of_measurement]):
            return JsonResponse({
                'error': 'All fields are required'
            }, status=400)

        # Parse month and year
        try:
            month = int(month)
            year = int(year)
            if not (1 <= month <= 12):
                raise ValueError("Month must be between 1 and 12")
            if not (2020 <= year <= 2050):
                raise ValueError("Year must be between 2020 and 2050")
        except (ValueError, TypeError) as e:
            return JsonResponse({
                'error': f'Invalid month or year: {str(e)}'
            }, status=400)

        # Parse objective value
        try:
            objective_value = float(objective_value)
        except (ValueError, TypeError):
            return JsonResponse({
                'error': 'Invalid objective value - must be a number'
            }, status=400)

        # Validate objective value is not negative
        if objective_value < 0:
            return JsonResponse({
                'error': 'Objective value must be greater than or equal to zero'
            }, status=400)

        # Get timezone from Settings
        timezone_str = Setting.get('default_timezone_for_monthly_objectives', 'America/Chicago')

        # Calculate start and end dates
        start_date = datetime(year, month, 1).date()
        last_day = monthrange(year, month)[1]
        end_date = datetime(year, month, last_day).date()

        # Generate objective_id from label, month, and year
        # Create slug from label
        label_slug = re.sub(r'[^\w\s-]', '', label.lower())
        label_slug = re.sub(r'[-\s]+', '_', label_slug).strip('_')

        # Get month abbreviation
        month_abbrev = datetime(year, month, 1).strftime('%b').lower()

        # Combine into objective_id
        objective_id = f"{label_slug}_{month_abbrev}_{year}"

        # Check if objective_id already exists
        if MonthlyObjective.objects.filter(objective_id=objective_id).exists():
            return JsonResponse({
                'error': f'An objective with this label already exists for {month_abbrev.capitalize()} {year}. Please use a different label.'
            }, status=400)

        # Create the objective
        objective = MonthlyObjective.objects.create(
            objective_id=objective_id,
            label=label,
            start=start_date,
            end=end_date,
            timezone=timezone_str,
            objective_value=objective_value,
            objective_definition=objective_definition,
            category=category,
            description=description,
            unit_of_measurement=unit_of_measurement,
            result=None  # Will be calculated later
        )

        # Check if this objective is in the current date range (from query params or session)
        # For simplicity, we'll just return a flag and let the frontend decide whether to reload
        in_current_range = False

        return JsonResponse({
            'success': True,
            'message': f'Objective "{label}" created successfully!',
            'objective_id': objective.objective_id,
            'in_current_range': in_current_range
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Error creating objective: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
def update_objective(request):
    """API endpoint to update an existing monthly objective."""
    import json
    import re
    from calendar import monthrange
    from monthly_objectives.models import MonthlyObjective
    from settings.models import Setting

    try:
        # Parse JSON data
        data = json.loads(request.body)

        # Extract and validate fields
        objective_id = data.get('objective_id', '').strip()
        label = data.get('label', '').strip()
        month = data.get('month', '')
        year = data.get('year', '')
        objective_value = data.get('objective_value', '')
        objective_definition = data.get('objective_definition', '').strip()
        category = data.get('category', '').strip() or None
        description = data.get('description', '').strip() or None
        unit_of_measurement = data.get('unit_of_measurement', '').strip() or None

        # Validate required fields
        if not all([objective_id, label, month, year, objective_value, objective_definition, category, description, unit_of_measurement]):
            return JsonResponse({
                'error': 'All fields are required'
            }, status=400)

        # Get the existing objective
        try:
            objective = MonthlyObjective.objects.get(objective_id=objective_id)
        except MonthlyObjective.DoesNotExist:
            return JsonResponse({
                'error': 'Objective not found'
            }, status=404)

        # Parse month and year
        try:
            month = int(month)
            year = int(year)
            if not (1 <= month <= 12):
                raise ValueError("Month must be between 1 and 12")
            if not (2020 <= year <= 2050):
                raise ValueError("Year must be between 2020 and 2050")
        except (ValueError, TypeError) as e:
            return JsonResponse({
                'error': f'Invalid month or year: {str(e)}'
            }, status=400)

        # Parse objective value
        try:
            objective_value = float(objective_value)
        except (ValueError, TypeError):
            return JsonResponse({
                'error': 'Invalid objective value - must be a number'
            }, status=400)

        # Validate objective value is not negative
        if objective_value < 0:
            return JsonResponse({
                'error': 'Objective value must be greater than or equal to zero'
            }, status=400)

        # Get timezone from Settings
        timezone_str = Setting.get('default_timezone_for_monthly_objectives', 'America/Chicago')

        # Calculate start and end dates
        start_date = datetime(year, month, 1).date()
        last_day = monthrange(year, month)[1]
        end_date = datetime(year, month, last_day).date()

        # Update the objective
        objective.label = label
        objective.start = start_date
        objective.end = end_date
        objective.timezone = timezone_str
        objective.objective_value = objective_value
        objective.objective_definition = objective_definition
        objective.category = category
        objective.description = description
        objective.unit_of_measurement = unit_of_measurement
        objective.save()

        # Re-calculate the result by running the SQL query
        from django.db import connection
        result = None
        try:
            with connection.cursor() as cursor:
                cursor.execute(objective_definition)
                row = cursor.fetchone()
                if row:
                    result = float(row[0]) if row[0] is not None else 0
        except Exception as e:
            # If SQL execution fails, result stays None
            pass

        # Calculate progress
        progress_pct = 0
        achieved = False
        if result is not None and objective_value > 0:
            progress_pct = round((result / objective_value) * 100, 1)
            achieved = result >= objective_value

        # Calculate target per week
        days_in_month = monthrange(year, month)[1]
        weeks_in_month = days_in_month / 7.0
        target_per_week = objective_value / weeks_in_month if weeks_in_month > 0 else 0

        return JsonResponse({
            'success': True,
            'message': f'Objective "{label}" updated successfully!',
            'objective_id': objective.objective_id,
            'in_current_range': False,
            'objective': {
                'label': label,
                'target': objective_value,
                'result': result if result is not None else 0,
                'progress_pct': progress_pct,
                'achieved': achieved,
                'month': month,
                'year': year,
                'objective_value': objective_value,
                'objective_definition': objective_definition,
                'category': category,
                'description': description,
                'unit': unit_of_measurement,
                'target_per_week': round(target_per_week, 1)
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Error updating objective: {str(e)}'
        }, status=500)


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
                'error': 'Objective not found'
            }, status=404)

        return JsonResponse({
            'success': True,
            'message': f'Objective "{objective_label}" deleted successfully!'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Error deleting objective: {str(e)}'
        }, status=500)
