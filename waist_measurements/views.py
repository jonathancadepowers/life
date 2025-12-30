from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime
from .models import WaistCircumferenceMeasurement
import uuid
import json


@require_http_methods(["POST"])
def log_measurement(request):
    """
    AJAX endpoint to log a waist circumference measurement.

    Expects JSON data:
        - log_date: string (YYYY-MM-DD format) - the date for the measurement
        - measurement: number - waist circumference in inches

    Returns JSON:
        - success: boolean
        - message: string
        - log_id: integer (if successful)
    """
    try:
        # Parse JSON request body
        data = json.loads(request.body)
        date_str = data.get('log_date')
        measurement = data.get('measurement')

        if not date_str:
            return JsonResponse({
                'success': False,
                'message': 'Date is required'
            }, status=400)

        if measurement is None:
            return JsonResponse({
                'success': False,
                'message': 'Measurement is required'
            }, status=400)

        # Parse the date string
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)

        # Validate measurement
        try:
            measurement_value = float(measurement)
            if measurement_value <= 0 or measurement_value > 100:
                raise ValueError("Measurement must be between 0 and 100 inches")
        except (ValueError, TypeError) as e:
            return JsonResponse({
                'success': False,
                'message': f'Invalid measurement value: {str(e)}'
            }, status=400)

        # Generate a unique source_id for manual entries
        source_id = str(uuid.uuid4())

        # Create the measurement entry
        log = WaistCircumferenceMeasurement.objects.create(
            source='Manual',
            source_id=source_id,
            log_date=selected_date,
            measurement=measurement_value
        )

        return JsonResponse({
            'success': True,
            'message': f'Waist measurement of {measurement_value}" logged successfully for {selected_date.strftime("%B %d, %Y")}!',
            'log_id': log.id,
            'log_date': selected_date.strftime('%Y-%m-%d'),
            'measurement': float(log.measurement)
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error logging measurement: {str(e)}'
        }, status=500)
