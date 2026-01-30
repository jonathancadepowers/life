import json
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import pytz

from .models import Task, TaskState, TaskTag
from calendar_events.models import CalendarEvent


def task_list(request):
    """Display all tasks."""
    tasks = Task.objects.select_related('state').prefetch_related('tags').all()
    states = TaskState.objects.all()
    tags = TaskTag.objects.all()

    # Get calendar events for today and nearby (let JS filter by local timezone)
    # Query a 48-hour window to handle all timezone edge cases
    now_utc = datetime.now(pytz.UTC)
    query_start = now_utc - timedelta(hours=24)
    query_end = now_utc + timedelta(hours=48)

    # Query events that overlap with this window
    calendar_events = CalendarEvent.objects.filter(
        start__lt=query_end,
        end__gt=query_start
    ).order_by('start')

    # Send UTC ISO timestamps - JavaScript will convert to local timezone
    events_data = []
    for event in calendar_events:
        events_data.append({
            'id': event.id,
            'subject': event.subject,
            'start': event.start.isoformat(),
            'end': event.end.isoformat(),
            'location': event.location,
            'is_all_day': event.is_all_day,
        })

    return render(request, 'todos/task_list.html', {
        'tasks': tasks,
        'states': states,
        'tags': tags,
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
                'tags': [],
                'calendar_start_time': task.calendar_start_time.isoformat() if task.calendar_start_time else None,
                'calendar_end_time': task.calendar_end_time.isoformat() if task.calendar_end_time else None,
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
        if 'calendar_start_time' in data:
            if data['calendar_start_time']:
                task.calendar_start_time = datetime.fromisoformat(data['calendar_start_time'].replace('Z', '+00:00'))
            else:
                task.calendar_start_time = None
        if 'calendar_end_time' in data:
            if data['calendar_end_time']:
                task.calendar_end_time = datetime.fromisoformat(data['calendar_end_time'].replace('Z', '+00:00'))
            else:
                task.calendar_end_time = None

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
                'tags': [{'id': t.id, 'name': t.name} for t in task.tags.all()],
                'calendar_start_time': task.calendar_start_time.isoformat() if task.calendar_start_time else None,
                'calendar_end_time': task.calendar_end_time.isoformat() if task.calendar_end_time else None,
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


def get_task(request, task_id):
    """Get a task's details via AJAX."""
    try:
        task = Task.objects.get(id=task_id)
        return JsonResponse({
            'success': True,
            'task': {
                'id': task.id,
                'title': task.title,
                'details': task.details,
                'critical': task.critical,
                'state_id': task.state_id,
                'state_name': task.state.name if task.state else None,
                'tags': [{'id': t.id, 'name': t.name} for t in task.tags.all()],
                'calendar_start_time': task.calendar_start_time.isoformat() if task.calendar_start_time else None,
                'calendar_end_time': task.calendar_end_time.isoformat() if task.calendar_end_time else None,
            }
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)


def list_states(request):
    """List all task states."""
    states = TaskState.objects.all()
    return JsonResponse({
        'success': True,
        'states': [{'id': s.id, 'name': s.name, 'order': s.order, 'bootstrap_icon': s.bootstrap_icon, 'task_count': s.tasks.count()} for s in states]
    })


def get_state_info(request, state_id):
    """Get info about a state including task count."""
    try:
        state = TaskState.objects.get(id=state_id)
        total_states = TaskState.objects.count()
        return JsonResponse({
            'success': True,
            'state': {
                'id': state.id,
                'name': state.name,
                'task_count': state.tasks.count(),
            },
            'total_states': total_states
        })
    except TaskState.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'State not found'}, status=404)


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


@require_http_methods(["DELETE", "POST"])
def delete_state(request, state_id):
    """Delete a task state via AJAX."""
    try:
        state = TaskState.objects.get(id=state_id)

        # Check if this is the last state
        if TaskState.objects.count() <= 1:
            return JsonResponse({'success': False, 'error': 'Cannot delete the last state'}, status=400)

        # Count tasks in this state
        task_count = Task.objects.filter(state=state).count()

        # If POST request, handle task migration
        if request.method == 'POST':
            data = json.loads(request.body)
            move_to_state_id = data.get('move_to_state_id')

            if task_count > 0 and move_to_state_id:
                try:
                    new_state = TaskState.objects.get(id=move_to_state_id)
                    Task.objects.filter(state=state).update(state=new_state)
                except TaskState.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Target state not found'}, status=404)

        state.delete()
        return JsonResponse({'success': True, 'task_count': task_count})
    except TaskState.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'State not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


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


def list_tags(request):
    """List all task tags."""
    tags = TaskTag.objects.all()
    return JsonResponse({
        'success': True,
        'tags': [{'id': t.id, 'name': t.name} for t in tags]
    })


@require_POST
def create_tag(request):
    """Create a new task tag via AJAX."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

        tag, created = TaskTag.objects.get_or_create(name=name)
        return JsonResponse({
            'success': True,
            'tag': {'id': tag.id, 'name': tag.name},
            'created': created
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_POST
def add_tag_to_task(request, task_id):
    """Add a tag to a task."""
    try:
        task = Task.objects.get(id=task_id)
        data = json.loads(request.body)
        tag_id = data.get('tag_id')

        if tag_id:
            tag = TaskTag.objects.get(id=tag_id)
            task.tags.add(tag)
        else:
            # Create new tag if name provided
            name = data.get('name', '').strip()
            if name:
                tag, _ = TaskTag.objects.get_or_create(name=name)
                task.tags.add(tag)
            else:
                return JsonResponse({'success': False, 'error': 'Tag ID or name required'}, status=400)

        return JsonResponse({
            'success': True,
            'task_tags': [{'id': t.id, 'name': t.name} for t in task.tags.all()]
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)
    except TaskTag.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tag not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_POST
def remove_tag_from_task(request, task_id):
    """Remove a tag from a task."""
    try:
        task = Task.objects.get(id=task_id)
        data = json.loads(request.body)
        tag_id = data.get('tag_id')

        if not tag_id:
            return JsonResponse({'success': False, 'error': 'Tag ID required'}, status=400)

        tag = TaskTag.objects.get(id=tag_id)
        task.tags.remove(tag)

        return JsonResponse({
            'success': True,
            'task_tags': [{'id': t.id, 'name': t.name} for t in task.tags.all()]
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)
    except TaskTag.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tag not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_http_methods(["DELETE"])
def delete_tag(request, tag_id):
    """Delete a tag."""
    try:
        tag = TaskTag.objects.get(id=tag_id)
        tag.delete()
        return JsonResponse({'success': True})
    except TaskTag.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tag not found'}, status=404)
