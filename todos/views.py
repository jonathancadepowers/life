import json
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import pytz

from .models import Task, TaskState, TaskTag, TimeBlock, TaskSchedule, TaskDetailTemplate, TaskView
from calendar_events.models import CalendarEvent


def serialize_task(task):
    """Serialize a task to a dictionary for JSON responses."""
    schedules = list(task.schedules.all())
    # For backward compatibility, derive calendar times from first schedule
    first_schedule = schedules[0] if schedules else None
    return {
        'id': task.id,
        'title': task.title,
        'details': task.details,
        'critical': task.critical,
        'state_id': task.state_id,
        'state_name': task.state.name if task.state else None,
        'tags': [{'id': t.id, 'name': t.name} for t in task.tags.all()],
        'deadline': task.deadline.isoformat() if task.deadline else None,
        'deadline_dismissed': task.deadline_dismissed,
        'state_changed_at': task.state_changed_at.isoformat() if task.state_changed_at else None,
        'updated_at': task.updated_at.isoformat() if task.updated_at else None,
        'calendar_start_time': first_schedule.start_time.isoformat() if first_schedule else None,
        'calendar_end_time': first_schedule.end_time.isoformat() if first_schedule else None,
        'schedules': [
            {
                'id': s.id,
                'start_time': s.start_time.isoformat(),
                'end_time': s.end_time.isoformat(),
            }
            for s in schedules
        ],
    }


def task_list(request):
    """Display all tasks."""
    tasks = Task.objects.select_related('state').prefetch_related('tags', 'schedules').all()
    states = TaskState.objects.all()
    tags = TaskTag.objects.all()
    detail_templates = TaskDetailTemplate.objects.all()

    # Get calendar events for today and nearby (let JS filter by local timezone)
    # Query a wider window to support browsing to past/future dates
    now_utc = datetime.now(pytz.UTC)
    query_start = now_utc - timedelta(days=7)  # 7 days back for browsing history
    query_end = now_utc + timedelta(days=7)    # 7 days forward for planning

    # Query events that overlap with this window (only active, not canceled)
    calendar_events = CalendarEvent.objects.filter(
        start__lt=query_end,
        end__gt=query_start,
        is_active=True
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

    # Query time blocks that overlap with this window (same 7-day range)
    time_blocks = TimeBlock.objects.filter(
        start_time__lt=query_end,
        end_time__gt=query_start
    ).order_by('start_time')

    time_blocks_data = []
    for block in time_blocks:
        time_blocks_data.append({
            'id': block.id,
            'name': block.name,
            'start': block.start_time.isoformat(),
            'end': block.end_time.isoformat(),
        })

    # Prepare templates data for JavaScript
    templates_data = []
    for template in detail_templates:
        templates_data.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'is_default': template.is_default,
        })

    # Prepare saved views data for JavaScript
    saved_views = TaskView.objects.all()
    views_data = []
    for view in saved_views:
        views_data.append({
            'id': view.id,
            'name': view.name,
            'settings': view.settings,
            'is_default': view.is_default,
        })

    return render(request, 'todos/task_list.html', {
        'tasks': tasks,
        'states': states,
        'tags': tags,
        'calendar_events': json.dumps(events_data),
        'time_blocks': json.dumps(time_blocks_data),
        'detail_templates': json.dumps(templates_data),
        'saved_views': json.dumps(views_data),
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
            'task': serialize_task(task)
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
            new_state_id = data['state_id']
            old_state_id = task.state_id
            if new_state_id != old_state_id:  # State actually changed
                task.state_changed_at = timezone.now()
            if new_state_id:
                task.state = TaskState.objects.get(id=new_state_id)
            else:
                task.state = None
        if 'deadline' in data:
            if data['deadline']:
                from datetime import date
                task.deadline = date.fromisoformat(data['deadline'])
            else:
                task.deadline = None
        if 'deadline_dismissed' in data:
            task.deadline_dismissed = data['deadline_dismissed']

        task.save()
        return JsonResponse({
            'success': True,
            'task': serialize_task(task)
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
        task = Task.objects.select_related('state').prefetch_related('tags', 'schedules').get(id=task_id)
        return JsonResponse({
            'success': True,
            'task': serialize_task(task)
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)


def list_states(request):
    """List all task states."""
    states = TaskState.objects.all()
    return JsonResponse({
        'success': True,
        'states': [{'id': s.id, 'name': s.name, 'order': s.order, 'bootstrap_icon': s.bootstrap_icon, 'is_system': s.is_system, 'is_terminal': s.is_terminal, 'task_count': s.tasks.count()} for s in states]
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
        if 'is_terminal' in data:
            # System states cannot be terminal
            if state.is_system and data['is_terminal']:
                return JsonResponse({'success': False, 'error': 'System states cannot be set as terminal'}, status=400)
            state.is_terminal = data['is_terminal']

        state.save()
        return JsonResponse({
            'success': True,
            'state': {
                'id': state.id,
                'name': state.name,
                'order': state.order,
                'bootstrap_icon': state.bootstrap_icon,
                'is_terminal': state.is_terminal,
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

        # Cannot delete system states (like Abandoned)
        if state.is_system:
            return JsonResponse({'success': False, 'error': 'Cannot delete system state'}, status=400)

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


@require_http_methods(["PATCH"])
def rename_tag(request, tag_id):
    """Rename a tag."""
    try:
        tag = TaskTag.objects.get(id=tag_id)
        data = json.loads(request.body)
        new_name = data.get('name', '').strip()

        if not new_name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

        # Check if tag name already exists
        if TaskTag.objects.filter(name=new_name).exclude(id=tag_id).exists():
            return JsonResponse({'success': False, 'error': 'Tag name already exists'}, status=400)

        tag.name = new_name
        tag.save()
        return JsonResponse({'success': True, 'tag': {'id': tag.id, 'name': tag.name}})
    except TaskTag.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tag not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


# ========== Time Block Views ==========

@require_POST
def create_time_block(request):
    """Create a new time block via AJAX."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        start_time = data.get('start_time')

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)
        if not start_time:
            return JsonResponse({'success': False, 'error': 'Start time is required'}, status=400)

        # Parse start time and calculate end time (30 minutes later)
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = start_dt + timedelta(minutes=30)

        time_block = TimeBlock.objects.create(
            name=name,
            start_time=start_dt,
            end_time=end_dt
        )

        return JsonResponse({
            'success': True,
            'time_block': {
                'id': time_block.id,
                'name': time_block.name,
                'start': time_block.start_time.isoformat(),
                'end': time_block.end_time.isoformat(),
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_http_methods(["PATCH"])
def update_time_block(request, block_id):
    """Update a time block via AJAX."""
    try:
        block = TimeBlock.objects.get(id=block_id)
        data = json.loads(request.body)

        if 'name' in data:
            block.name = data['name'].strip()
        if 'start_time' in data:
            if data['start_time']:
                block.start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            else:
                return JsonResponse({'success': False, 'error': 'Start time cannot be empty'}, status=400)
        if 'end_time' in data:
            if data['end_time']:
                block.end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            else:
                return JsonResponse({'success': False, 'error': 'End time cannot be empty'}, status=400)

        block.save()
        return JsonResponse({
            'success': True,
            'time_block': {
                'id': block.id,
                'name': block.name,
                'start': block.start_time.isoformat(),
                'end': block.end_time.isoformat(),
            }
        })
    except TimeBlock.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Time block not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_http_methods(["DELETE"])
def delete_time_block(request, block_id):
    """Delete a time block via AJAX."""
    try:
        block = TimeBlock.objects.get(id=block_id)
        block.delete()
        return JsonResponse({'success': True})
    except TimeBlock.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Time block not found'}, status=404)


# ========== Task Schedule Views ==========

@require_POST
def create_task_schedule(request, task_id):
    """Create a new schedule for a task via AJAX."""
    try:
        task = Task.objects.get(id=task_id)
        data = json.loads(request.body)

        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if not start_time:
            return JsonResponse({'success': False, 'error': 'Start time is required'}, status=400)
        if not end_time:
            return JsonResponse({'success': False, 'error': 'End time is required'}, status=400)

        # Parse times
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))

        schedule = TaskSchedule.objects.create(
            task=task,
            start_time=start_dt,
            end_time=end_dt
        )

        return JsonResponse({
            'success': True,
            'schedule': {
                'id': schedule.id,
                'start_time': schedule.start_time.isoformat(),
                'end_time': schedule.end_time.isoformat(),
            },
            'task': serialize_task(task)
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_http_methods(["PATCH"])
def update_task_first_schedule(request, task_id):
    """Update the first schedule for a task via AJAX (convenience endpoint for frontend)."""
    try:
        task = Task.objects.prefetch_related('schedules').get(id=task_id)
        schedule = task.schedules.first()
        if not schedule:
            return JsonResponse({'success': False, 'error': 'No schedule found for this task'}, status=404)

        data = json.loads(request.body)

        if 'start_time' in data:
            if data['start_time']:
                schedule.start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            else:
                return JsonResponse({'success': False, 'error': 'Start time cannot be empty'}, status=400)
        if 'end_time' in data:
            if data['end_time']:
                schedule.end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            else:
                return JsonResponse({'success': False, 'error': 'End time cannot be empty'}, status=400)

        schedule.save()

        return JsonResponse({
            'success': True,
            'schedule': {
                'id': schedule.id,
                'start_time': schedule.start_time.isoformat(),
                'end_time': schedule.end_time.isoformat(),
            },
            'task': serialize_task(task)
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_http_methods(["PATCH"])
def update_task_schedule(request, schedule_id):
    """Update a task schedule via AJAX."""
    try:
        schedule = TaskSchedule.objects.select_related('task').get(id=schedule_id)
        data = json.loads(request.body)

        if 'start_time' in data:
            if data['start_time']:
                schedule.start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            else:
                return JsonResponse({'success': False, 'error': 'Start time cannot be empty'}, status=400)
        if 'end_time' in data:
            if data['end_time']:
                schedule.end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            else:
                return JsonResponse({'success': False, 'error': 'End time cannot be empty'}, status=400)

        schedule.save()

        return JsonResponse({
            'success': True,
            'schedule': {
                'id': schedule.id,
                'start_time': schedule.start_time.isoformat(),
                'end_time': schedule.end_time.isoformat(),
            },
            'task': serialize_task(schedule.task)
        })
    except TaskSchedule.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Schedule not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_http_methods(["DELETE"])
def delete_task_schedule(request, schedule_id):
    """Delete a task schedule via AJAX."""
    try:
        schedule = TaskSchedule.objects.select_related('task').get(id=schedule_id)
        task = schedule.task
        schedule.delete()

        return JsonResponse({
            'success': True,
            'task': serialize_task(task)
        })
    except TaskSchedule.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Schedule not found'}, status=404)


@require_http_methods(["DELETE"])
def delete_task_schedules(request, task_id):
    """Delete all schedules for a task via AJAX."""
    try:
        task = Task.objects.prefetch_related('schedules').get(id=task_id)
        task.schedules.all().delete()

        return JsonResponse({
            'success': True,
            'task': serialize_task(task)
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)


# ========== Task Detail Template Views ==========

def list_templates(request):
    """List all task detail templates."""
    templates = TaskDetailTemplate.objects.all()
    return JsonResponse({
        'success': True,
        'templates': [
            {
                'id': t.id,
                'name': t.name,
                'content': t.content,
                'is_default': t.is_default,
                'order': t.order,
            }
            for t in templates
        ]
    })


@require_POST
def create_template(request):
    """Create a new task detail template via AJAX."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        content = data.get('content', '')
        is_default = data.get('is_default', False)

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

        # Set order to be at the end
        max_order = TaskDetailTemplate.objects.count()
        template = TaskDetailTemplate.objects.create(
            name=name,
            content=content,
            is_default=is_default,
            order=max_order
        )

        return JsonResponse({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'content': template.content,
                'is_default': template.is_default,
                'order': template.order,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_http_methods(["PATCH"])
def update_template(request, template_id):
    """Update a task detail template via AJAX."""
    try:
        template = TaskDetailTemplate.objects.get(id=template_id)
        data = json.loads(request.body)

        if 'name' in data:
            template.name = data['name'].strip()
        if 'content' in data:
            template.content = data['content']
        if 'is_default' in data:
            template.is_default = data['is_default']

        template.save()

        return JsonResponse({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'content': template.content,
                'is_default': template.is_default,
                'order': template.order,
            }
        })
    except TaskDetailTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Template not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_http_methods(["DELETE"])
def delete_template(request, template_id):
    """Delete a task detail template via AJAX."""
    try:
        template = TaskDetailTemplate.objects.get(id=template_id)
        template.delete()
        return JsonResponse({'success': True})
    except TaskDetailTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Template not found'}, status=404)


# Task Views (saved filter configurations)
def list_views(request):
    """List all saved task views."""
    views = TaskView.objects.all()
    return JsonResponse({
        'success': True,
        'views': [
            {
                'id': v.id,
                'name': v.name,
                'settings': v.settings,
                'is_default': v.is_default,
                'order': v.order,
            }
            for v in views
        ]
    })


@require_POST
def create_view(request):
    """Create a new saved task view via AJAX."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        settings = data.get('settings', {})
        is_default = data.get('is_default', False)

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

        # Set order to be at the end
        max_order = TaskView.objects.count()
        view = TaskView.objects.create(
            name=name,
            settings=settings,
            is_default=is_default,
            order=max_order
        )

        return JsonResponse({
            'success': True,
            'view': {
                'id': view.id,
                'name': view.name,
                'settings': view.settings,
                'is_default': view.is_default,
                'order': view.order,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_http_methods(["DELETE"])
def delete_view(request, view_id):
    """Delete a saved task view via AJAX."""
    try:
        view = TaskView.objects.get(id=view_id)
        view.delete()
        return JsonResponse({'success': True})
    except TaskView.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'View not found'}, status=404)


# ========== Abandoned Tasks ==========

@require_POST
def process_abandoned_tasks(request):
    """Process tasks that should be marked as abandoned based on time threshold."""
    try:
        data = json.loads(request.body)
        abandoned_days = data.get('abandoned_days', 14)

        # Get or create the Abandoned state (system state)
        abandoned_state, created = TaskState.objects.get_or_create(
            name='Abandoned',
            defaults={
                'order': 999,  # Very high to ensure it's always last
                'bootstrap_icon': 'bi-archive',
                'is_system': True
            }
        )

        # Find terminal state (last non-system state by order)
        terminal_state = TaskState.objects.filter(
            is_system=False
        ).order_by('-order').first()

        if not terminal_state:
            return JsonResponse({
                'success': True,
                'abandoned_count': 0,
                'abandoned_state_id': abandoned_state.id if abandoned_state.tasks.exists() else None
            })

        # Find tasks that should be abandoned
        # Tasks where updated_at < (now - X days) - any edit resets the timer
        # Excluding: terminal state, already abandoned, no state
        threshold_date = timezone.now() - timedelta(days=abandoned_days)

        tasks_to_abandon = Task.objects.filter(
            updated_at__lt=threshold_date
        ).exclude(
            state=terminal_state  # Not already completed
        ).exclude(
            state=abandoned_state  # Not already abandoned
        ).exclude(
            state__isnull=True  # Has a state
        )

        # Move them to abandoned state
        count = tasks_to_abandon.count()
        if count > 0:
            tasks_to_abandon.update(
                state=abandoned_state,
                state_changed_at=timezone.now()
            )

        return JsonResponse({
            'success': True,
            'abandoned_count': count,
            'abandoned_state_id': abandoned_state.id if abandoned_state.tasks.exists() else None
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
