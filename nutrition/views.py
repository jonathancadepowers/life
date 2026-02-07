from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime
from .models import NutritionEntry
import uuid
import pytz


@require_http_methods(["POST"])
def log_nutrition(request):
    """
    AJAX endpoint to log a new nutrition entry.

    Expects POST data:
        - calories: decimal
        - fat: decimal
        - carbs: decimal
        - protein: decimal
        - date: string (YYYY-MM-DD format) - the date for the nutrition entry

    Returns JSON:
        - success: boolean
        - message: string
        - entry_id: integer (if successful)
    """
    try:
        # Get nutrition data from POST
        calories = request.POST.get('calories')
        fat = request.POST.get('fat')
        carbs = request.POST.get('carbs')
        protein = request.POST.get('protein')
        date_str = request.POST.get('date')

        # Validate required fields
        if not all([calories, fat, carbs, protein, date_str]):
            return JsonResponse({
                'success': False,
                'message': 'All fields are required'
            }, status=400)

        # Validate numeric values
        try:
            calories = float(calories)
            fat = float(fat)
            carbs = float(carbs)
            protein = float(protein)
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Nutrition values must be valid numbers'
            }, status=400)

        # Validate non-negative values
        if any(value < 0 for value in [calories, fat, carbs, protein]):
            return JsonResponse({
                'success': False,
                'message': 'Nutrition values cannot be negative'
            }, status=400)

        # Parse the date string
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)

        # Get user's timezone from cookie (set by browser), default to America/Chicago (CST)
        user_tz_str = request.COOKIES.get('user_timezone', 'America/Chicago')
        try:
            user_tz = pytz.timezone(user_tz_str)
        except pytz.exceptions.UnknownTimeZoneError:
            user_tz = pytz.timezone('America/Chicago')

        # Consumption date is at 12:00 PM (noon) on the selected date in user's timezone
        # Create a naive datetime at noon on the selected date
        from datetime import time
        consumption_date_naive = datetime.combine(selected_date, time(12, 0))

        # Localize to user's timezone (this handles DST correctly)
        consumption_date = user_tz.localize(consumption_date_naive)

        # Generate a unique source_id for manual entries
        source_id = str(uuid.uuid4())

        # Create nutrition entry
        entry = NutritionEntry.objects.create(
            source='Manual',
            source_id=source_id,
            consumption_date=consumption_date,
            calories=calories,
            fat=fat,
            carbs=carbs,
            protein=protein
        )

        return JsonResponse({
            'success': True,
            'message': f'Nutrition entry logged successfully for {selected_date.strftime("%B %d, %Y")}!',
            'entry_id': entry.id,
            'calories': float(entry.calories),
            'fat': float(entry.fat),
            'carbs': float(entry.carbs),
            'protein': float(entry.protein),
            'consumption_date': consumption_date.strftime('%Y-%m-%d %H:%M')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error logging nutrition: {str(e)}'
        }, status=500)
