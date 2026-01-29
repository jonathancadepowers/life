import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import Task, TaskContext


def task_list(request):
    """Display all tasks."""
    tasks = Task.objects.select_related('context').all()
    contexts = TaskContext.objects.all()
    return render(request, 'todos/task_list.html', {'tasks': tasks, 'contexts': contexts})


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
        'contexts': [{'id': c.id, 'name': c.name} for c in contexts]
    })


@require_POST
def create_context(request):
    """Create a new task context via AJAX."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

        context, created = TaskContext.objects.get_or_create(name=name)
        if not created:
            return JsonResponse({'success': False, 'error': 'Context already exists'}, status=400)

        return JsonResponse({
            'success': True,
            'context': {
                'id': context.id,
                'name': context.name,
            }
        })
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
