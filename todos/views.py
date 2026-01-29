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

        task = Task.objects.create(title=title)
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
            }
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)
    except TaskContext.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Context not found'}, status=404)
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
        'states': [{'id': s.id, 'name': s.name, 'is_terminal': s.is_terminal} for s in states]
    })


@require_POST
def create_state(request):
    """Create a new task state via AJAX."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

        state, created = TaskState.objects.get_or_create(name=name)
        if not created:
            return JsonResponse({'success': False, 'error': 'State already exists'}, status=400)

        return JsonResponse({
            'success': True,
            'state': {
                'id': state.id,
                'name': state.name,
                'is_terminal': state.is_terminal,
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
        if 'is_terminal' in data:
            if data['is_terminal']:
                # Check if another state is already terminal
                existing_terminal = TaskState.objects.filter(is_terminal=True).exclude(id=state_id).first()
                if existing_terminal:
                    return JsonResponse({
                        'success': False,
                        'error': f'"{existing_terminal.name}" is already marked as terminal. Unmark it first.'
                    }, status=400)
            state.is_terminal = data['is_terminal']

        state.save()
        return JsonResponse({
            'success': True,
            'state': {
                'id': state.id,
                'name': state.name,
                'is_terminal': state.is_terminal,
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
