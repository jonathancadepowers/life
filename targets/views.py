from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import date, datetime, timedelta
from .models import Target, DailyAgenda
from projects.models import Project
from goals.models import Goal
from time_logs.models import TimeLog


def set_agenda(request):
    """View to set today's agenda with 3 targets."""
    today = date.today()

    if request.method == 'POST':
        # Get or create today's agenda
        agenda, created = DailyAgenda.objects.get_or_create(date=today)

        # Process each target
        for i in range(1, 4):
            project_id = request.POST.get(f'project_{i}')
            goal_id = request.POST.get(f'goal_{i}')
            target_input = request.POST.get(f'target_{i}')

            if project_id and goal_id and target_input:
                # Get or create target
                target, _ = Target.objects.get_or_create(
                    target_id=target_input,
                    defaults={
                        'target_name': target_input,
                        'goal_id_id': goal_id
                    }
                )

                # Set agenda fields
                setattr(agenda, f'project_{i}_id', project_id)
                setattr(agenda, f'goal_{i}_id', goal_id)
                setattr(agenda, f'target_{i}', target)

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

    if not project_id:
        return JsonResponse({'goals': []})

    # Find goals that have been used with this project in time logs
    goal_ids = TimeLog.objects.filter(
        project_id=project_id
    ).values_list('goals__goal_id', flat=True).distinct()

    goals = Goal.objects.filter(goal_id__in=goal_ids).values('goal_id', 'display_string')

    return JsonResponse({'goals': list(goals)})


def get_targets_for_goal(request):
    """AJAX endpoint to get targets associated with a goal."""
    goal_id = request.GET.get('goal_id')

    if not goal_id:
        return JsonResponse({'targets': []})

    targets = Target.objects.filter(goal_id=goal_id).values('target_id', 'target_name')

    return JsonResponse({'targets': list(targets)})


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
                # Get or create target (goal_id is optional)
                # Use goal_id if provided, otherwise use a default goal or None
                target_goal_id = goal_id if goal_id else None

                # Create a unique target_id that includes timestamp to allow duplicates
                # Target_id should be unique per target entry
                from datetime import datetime
                unique_target_id = f"{target_input}_{datetime.now().timestamp()}"

                # Get or create target
                target, _ = Target.objects.get_or_create(
                    target_id=unique_target_id,
                    defaults={
                        'target_name': target_input,
                        'goal_id_id': target_goal_id
                    }
                )

                # Set agenda fields
                setattr(agenda, f'project_{i}_id', project_id)
                setattr(agenda, f'goal_{i}_id', goal_id if goal_id else None)
                setattr(agenda, f'target_{i}', target)
            else:
                # Clear fields if not provided
                setattr(agenda, f'project_{i}_id', None)
                setattr(agenda, f'goal_{i}_id', None)
                setattr(agenda, f'target_{i}', None)
                # Also clear the score if target is removed
                setattr(agenda, f'target_{i}_score', None)

        # Save notes if provided
        notes = request.POST.get('notes', '')
        agenda.notes = notes

        agenda.save()

        return JsonResponse({
            'success': True,
            'message': 'Today\'s agenda has been set!'
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
        goal_id = request.GET.get('goal_id')  # This is the tag name in Toggl
        timezone_offset = request.GET.get('timezone_offset')  # User's timezone offset in minutes
        date_str = request.GET.get('date')  # Optional: specific date to query (YYYY-MM-DD)

        if not project_id:
            return JsonResponse({'error': 'project_id is required'}, status=400)

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

                # If goal_id is specified, check if entry has this tag
                if goal_id and goal_id not in entry_tags:
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
                'day_score': agenda.day_score,
                'notes': agenda.notes,
                'targets': []
            }

            # Add each target's data
            for i in range(1, 4):
                project = getattr(agenda, f'project_{i}')
                goal = getattr(agenda, f'goal_{i}')
                target = getattr(agenda, f'target_{i}')

                target_data = {
                    'project_id': project.project_id if project else None,
                    'project_name': project.display_string if project else None,
                    'goal_id': goal.goal_id if goal else None,
                    'goal_name': goal.display_string if goal else None,
                    'target_id': target.target_id if target else None,
                    'target_name': target.target_name if target else None
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

        # Validate target_num
        try:
            target_num = int(target_num)
            if target_num not in [1, 2, 3]:
                raise ValueError()
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'target_num must be 1, 2, or 3'
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

        # Set the score for the specified target
        setattr(agenda, f'target_{target_num}_score', score)

        # Calculate and save overall day score
        # Count how many targets are set
        targets_set = 0
        total_score = 0

        for i in range(1, 4):
            target = getattr(agenda, f'target_{i}')
            target_score = getattr(agenda, f'target_{i}_score')

            # Target is set if it exists
            if target:
                targets_set += 1
                # Add score if it exists (0, 0.5, or 1)
                if target_score is not None:
                    total_score += target_score

        # Calculate day score if any targets are set
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
