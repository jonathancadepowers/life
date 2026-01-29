import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import Task, TaskContext, TaskState


def task_list(request):
    """Display all tasks."""
    tasks = Task.objects.select_related('context', 'state').all()
    contexts = TaskContext.objects.all()
    states = TaskState.objects.all()
    return render(request, 'todos/task_list.html', {'tasks': tasks, 'contexts': contexts, 'states': states})


@require_POST
def create_task(request):
    """Create a new task via AJAX."""
    try:
        data = json.loads(request.body)
        title = data.get('title', '').strip()

        if not title:
            return JsonResponse({'success': False, 'error': 'Title is required'}, status=400)

        # Get Inbox state for new tasks
        inbox_state = TaskState.objects.filter(name='Inbox').first()
        task = Task.objects.create(title=title, state=inbox_state)
        return JsonResponse({
            'success': True,
            'task': {
                'id': task.id,
                'title': task.title,
                'details': task.details,
                'critical': task.critical,
                'context_id': None,
                'context_name': None,
                'context_color': None,
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
        if 'context_id' in data:
            if data['context_id']:
                task.context = TaskContext.objects.get(id=data['context_id'])
            else:
                task.context = None
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
                'context_id': task.context_id,
                'context_name': task.context.name if task.context else None,
                'context_color': task.context.color if task.context else None,
                'state_id': task.state_id,
                'state_name': task.state.name if task.state else None,
            }
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)
    except TaskContext.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Context not found'}, status=404)
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


def list_contexts(request):
    """List all task contexts."""
    contexts = TaskContext.objects.all()
    return JsonResponse({
        'success': True,
        'contexts': [{'id': c.id, 'name': c.name, 'color': c.color} for c in contexts]
    })


@require_POST
def create_context(request):
    """Create a new task context via AJAX."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        color = data.get('color', '#6c757d')

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

        context, created = TaskContext.objects.get_or_create(
            name=name,
            defaults={'color': color}
        )
        if not created:
            return JsonResponse({'success': False, 'error': 'Context already exists'}, status=400)

        return JsonResponse({
            'success': True,
            'context': {
                'id': context.id,
                'name': context.name,
                'color': context.color,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_http_methods(["PATCH"])
def update_context(request, context_id):
    """Update a task context via AJAX."""
    try:
        context = TaskContext.objects.get(id=context_id)
        data = json.loads(request.body)

        if 'name' in data:
            context.name = data['name'].strip()
        if 'color' in data:
            context.color = data['color']

        context.save()
        return JsonResponse({
            'success': True,
            'context': {
                'id': context.id,
                'name': context.name,
                'color': context.color,
            }
        })
    except TaskContext.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Context not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@require_http_methods(["DELETE"])
def delete_context(request, context_id):
    """Delete a task context via AJAX."""
    try:
        context = TaskContext.objects.get(id=context_id)
        context.delete()
        return JsonResponse({'success': True})
    except TaskContext.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Context not found'}, status=404)


def list_states(request):
    """List all task states."""
    states = TaskState.objects.all()
    return JsonResponse({
        'success': True,
        'states': [{'id': s.id, 'name': s.name, 'is_terminal': s.is_terminal, 'order': s.order, 'bootstrap_icon': s.bootstrap_icon} for s in states]
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

        # Set order to be after all non-terminal states but before terminal
        max_order = TaskState.objects.filter(is_terminal=False).count()
        state = TaskState.objects.create(name=name, order=max_order)

        return JsonResponse({
            'success': True,
            'state': {
                'id': state.id,
                'name': state.name,
                'is_terminal': state.is_terminal,
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

        # Prevent modifying Inbox
        if state.name == 'Inbox':
            if 'name' in data and data['name'].strip() != 'Inbox':
                return JsonResponse({'success': False, 'error': 'Cannot rename Inbox'}, status=400)
            if 'is_terminal' in data and data['is_terminal']:
                return JsonResponse({'success': False, 'error': 'Cannot make Inbox terminal'}, status=400)

        if 'name' in data:
            state.name = data['name'].strip()
        if 'is_terminal' in data:
            if data['is_terminal']:
                # Check if another state is already terminal
                existing_terminal = TaskState.objects.filter(is_terminal=True).exclude(id=state_id).first()
                if existing_terminal:
                    return JsonResponse({
                        'success': False,
                        'error': f'"{existing_terminal.name}" is already marked as terminal. Unmark it first.'
                    }, status=400)
                # Terminal state gets highest order
                state.order = 9999
            state.is_terminal = data['is_terminal']
        if 'bootstrap_icon' in data:
            state.bootstrap_icon = data['bootstrap_icon'].strip() if data['bootstrap_icon'] else ''

        state.save()
        return JsonResponse({
            'success': True,
            'state': {
                'id': state.id,
                'name': state.name,
                'is_terminal': state.is_terminal,
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
        # Prevent deleting Inbox
        if state.name == 'Inbox':
            return JsonResponse({'success': False, 'error': 'Cannot delete the Inbox state'}, status=400)
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

        # Reorder, but Inbox always stays at 0
        for index, state_id in enumerate(order_list):
            state = TaskState.objects.filter(id=state_id, is_terminal=False).first()
            if state and state.name != 'Inbox':
                state.order = index + 1  # +1 because Inbox is at 0
                state.save()

        # Ensure Inbox stays at order 0
        TaskState.objects.filter(name='Inbox').update(order=0)

        # Ensure terminal state stays at the end
        TaskState.objects.filter(is_terminal=True).update(order=9999)

        return JsonResponse({'success': True})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
