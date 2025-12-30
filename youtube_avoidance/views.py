from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime
from .models import YouTubeAvoidanceLog
import uuid


@require_http_methods(["POST"])
def log_youtube(request):
    """
    AJAX endpoint to log a YouTube avoidance entry.

    Expects POST data:
        - date: string (YYYY-MM-DD format) - the date for the log entry

    Returns JSON:
        - success: boolean
        - message: string
        - log_id: integer (if successful)
    """
    try:
        # Get the date from POST data
        date_str = request.POST.get('date')

        if not date_str:
            return JsonResponse({
                'success': False,
                'message': 'Date is required'
            }, status=400)

        # Parse the date string
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)

        # Generate a unique source_id for manual entries
        source_id = str(uuid.uuid4())

        # Create the log entry
        log = YouTubeAvoidanceLog.objects.create(
            source='Manual',
            source_id=source_id,
            log_date=selected_date,
        )

        return JsonResponse({
            'success': True,
            'message': f'YouTube avoidance logged successfully for {selected_date.strftime("%B %d, %Y")}!',
            'log_id': log.id,
            'log_date': selected_date.strftime('%Y-%m-%d')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error logging YouTube avoidance: {str(e)}'
        }, status=500)
