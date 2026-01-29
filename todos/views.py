import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import Task


def task_list(request):
    """Display all tasks."""
    tasks = Task.objects.all()
    return render(request, 'todos/task_list.html', {'tasks': tasks})


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

        task.save()
        return JsonResponse({
            'success': True,
            'task': {
                'id': task.id,
                'title': task.title,
                'details': task.details,
                'critical': task.critical,
            }
        })
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)
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
