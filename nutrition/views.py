from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime
from .models import NutritionEntry
import uuid


@require_http_methods(["POST"])
def log_nutrition(request):
    """
    AJAX endpoint to log a new nutrition entry.

    Expects POST data:
        - calories: decimal
        - fat: decimal
        - carbs: decimal
        - protein: decimal
        - consumption_date: ISO 8601 datetime string

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
        consumption_date_str = request.POST.get('consumption_date')

        # Validate required fields
        if not all([calories, fat, carbs, protein, consumption_date_str]):
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

        # Parse consumption date
        try:
            # Try parsing ISO format with timezone
            consumption_date = datetime.fromisoformat(consumption_date_str.replace('Z', '+00:00'))
            # Make aware if naive
            if timezone.is_naive(consumption_date):
                consumption_date = timezone.make_aware(consumption_date)
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid date format'
            }, status=400)

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
            'message': 'Nutrition entry logged successfully!',
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
