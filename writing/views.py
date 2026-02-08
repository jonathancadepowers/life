from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import datetime
import uuid

from .models import WritingLog


@require_POST
def create_writing_log(request):
    """
    Create a new writing log entry.
    Expects JSON with: { "log_date": "YYYY-MM-DD" }
    """
    try:
        import json
        data = json.loads(request.body)
        log_date_str = data.get('log_date')

        if not log_date_str:
            return JsonResponse({'success': False, 'error': 'log_date is required'}, status=400)

        # Parse the date
        log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()

        # Generate a unique UUID for source_id
        source_id = str(uuid.uuid4())

        # Create the writing log
        writing_log = WritingLog.objects.create(
            source='Manual',
            source_id=source_id,
            log_date=log_date,
            duration=1.5
        )

        return JsonResponse({
            'success': True,
            'id': writing_log.id,
            'log_date': str(writing_log.log_date),
            'source_id': writing_log.source_id
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': f'Invalid date format: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
