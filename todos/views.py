import json
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import pytz

from .models import Task, TaskState
from calendar_events.models import CalendarEvent


def task_list(request):
    """Display all tasks."""
    tasks = Task.objects.select_related('state').all()
    states = TaskState.objects.all()

    # Get today's calendar events in CST
    cst = pytz.timezone('America/Chicago')
    now_cst = datetime.now(cst)
    today_start_cst = now_cst.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end_cst = today_start_cst + timedelta(days=1)

    # Convert to UTC for database query
    today_start_utc = today_start_cst.astimezone(pytz.UTC)
    today_end_utc = today_end_cst.astimezone(pytz.UTC)

    # Query events that overlap with today (in UTC)
    calendar_events = CalendarEvent.objects.filter(
        start__lt=today_end_utc,
        end__gt=today_start_utc
    ).order_by('start')

    # Convert events to CST for template
    events_data = []
    for event in calendar_events:
        start_cst = event.start.astimezone(cst)
        end_cst = event.end.astimezone(cst)
        events_data.append({
            'id': event.id,
            'subject': event.subject,
            'start_hour': start_cst.hour,
            'start_minute': start_cst.minute,
            'end_hour': end_cst.hour,
            'end_minute': end_cst.minute,
            'location': event.location,
            'is_all_day': event.is_all_day,
        })

    return render(request, 'todos/task_list.html', {
        'tasks': tasks,
        'states': states,
        'calendar_events': json.dumps(events_data),
    })


@require_POST
def create_task(request):
    """Create a new task via AJAX."""
    try:
        data = json.loads(request.body)
        title = data.get('title', '').strip()

        if not title:
            return JsonResponse({'success': False, 'error': 'Title is required'}, status=400)

        # Get first state by order for new tasks
        first_state = TaskState.objects.first()
        task = Task.objects.create(title=title, state=first_state)
        return JsonResponse({
            'success': True,
            'task': {
                'id': task.id,
                'title': task.title,
                'details': task.details,
                'critical': task.critical,
                'state_id': task.state_id,
                'state_name': task.state.name if task.state else None,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_http_methods(["PATCH"])
def update_task(request, task_id):
    """Update a task via AJAX."""
    try:
        task = Task.objects.get(id=task_id)
        data = json.loads(request.body)

        if 'title' in data:
            task.title = data['title'].strip()
        if 'details' in data:
            task.details = data['details']
        if 'critical' in data:
            task.critical = data['critical']
        if 'state_id' in data:
            if data['state_id']:
                task.state = TaskState.objects.get(id=data['state_id'])
            else:
                task.state = None

        task.save()
        return JsonResponse({
            'success': True,
            'task': {
                'id': task.id,
                'title': task.title,
                'details': task.details,
                'critical': task.critical,
                'state_id': task.state_id,
                'state_name': task.state.name if task.state else None,
            }
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)
    except TaskState.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'State not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_http_methods(["DELETE"])
def delete_task(request, task_id):
    """Delete a task via AJAX."""
    try:
        task = Task.objects.get(id=task_id)
        task.delete()
        return JsonResponse({'success': True})
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)


def list_states(request):
    """List all task states."""
    states = TaskState.objects.all()
    return JsonResponse({
        'success': True,
        'states': [{'id': s.id, 'name': s.name, 'order': s.order, 'bootstrap_icon': s.bootstrap_icon} for s in states]
    })


@require_POST
def create_state(request):
    """Create a new task state via AJAX."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

        # Check if state already exists
        if TaskState.objects.filter(name=name).exists():
            return JsonResponse({'success': False, 'error': 'State already exists'}, status=400)

        # Set order to be at the end
        max_order = TaskState.objects.count()
        state = TaskState.objects.create(name=name, order=max_order)

        return JsonResponse({
            'success': True,
            'state': {
                'id': state.id,
                'name': state.name,
                'order': state.order,
                'bootstrap_icon': state.bootstrap_icon,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_http_methods(["PATCH"])
def update_state(request, state_id):
    """Update a task state via AJAX."""
    try:
        state = TaskState.objects.get(id=state_id)
        data = json.loads(request.body)

        if 'name' in data:
            state.name = data['name'].strip()
        if 'bootstrap_icon' in data:
            state.bootstrap_icon = data['bootstrap_icon'].strip() if data['bootstrap_icon'] else ''

        state.save()
        return JsonResponse({
            'success': True,
            'state': {
                'id': state.id,
                'name': state.name,
                'order': state.order,
                'bootstrap_icon': state.bootstrap_icon,
            }
        })
    except TaskState.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'State not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_http_methods(["DELETE"])
def delete_state(request, state_id):
    """Delete a task state via AJAX."""
    try:
        state = TaskState.objects.get(id=state_id)
        state.delete()
        return JsonResponse({'success': True})
    except TaskState.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'State not found'}, status=404)


@require_POST
def reorder_states(request):
    """Reorder task states via AJAX."""
    try:
        data = json.loads(request.body)
        order_list = data.get('order', [])  # List of state IDs in new order

        for index, state_id in enumerate(order_list):
            TaskState.objects.filter(id=state_id).update(order=index)

        return JsonResponse({'success': True})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_POST
def reorder_tasks(request):
    """Reorder tasks within a state/column via AJAX."""
    try:
        data = json.loads(request.body)
        task_ids = data.get('task_ids', [])  # List of task IDs in new order

        for index, task_id in enumerate(task_ids):
            Task.objects.filter(id=task_id).update(order=index)

        return JsonResponse({'success': True})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
