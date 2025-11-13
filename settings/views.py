from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import connection
from .models import LifeTrackerColumn


def life_tracker_settings(request):
    """View for configuring Life Tracker column settings."""
    if request.method == 'POST':
        # Handle form submission
        column_name = request.POST.get('column_name')
        if column_name:
            column = get_object_or_404(LifeTrackerColumn, pk=column_name)
            column.display_name = request.POST.get('display_name', column.display_name)
            column.tooltip_text = request.POST.get('tooltip_text', column.tooltip_text)
            column.sql_query = request.POST.get('sql_query', column.sql_query)
            column.order = int(request.POST.get('order', column.order))
            column.enabled = request.POST.get('enabled') == 'on'

            # Validate SQL query
            try:
                # Test the query with sample parameters
                from datetime import datetime
                import pytz
                user_tz = pytz.timezone('America/Los_Angeles')
                test_date = datetime(2025, 1, 1)
                day_start = user_tz.localize(datetime.combine(test_date, datetime.min.time()))
                day_end = user_tz.localize(datetime.combine(test_date, datetime.max.time()))

                with connection.cursor() as cursor:
                    # Replace named parameters with positional ones for testing
                    test_query = column.sql_query.replace(':day_start', '%s').replace(':day_end', '%s')
                    cursor.execute(test_query, [day_start, day_end])
                    result = cursor.fetchone()

                    # Verify it returns a numeric result
                    if result is None or not isinstance(result[0], (int, float, type(None))):
                        raise ValueError("Query must return a count (numeric value)")

                column.save()
                messages.success(request, f'Successfully updated {column.display_name} settings.')
            except Exception as e:
                messages.error(request, f'Invalid SQL query: {str(e)}')

        return redirect('life_tracker_settings')

    # Get all columns ordered
    columns = LifeTrackerColumn.objects.all()

    context = {
        'columns': columns,
        'available_parameters': [
            ':day_start - Start of the day in user\'s timezone (timezone-aware datetime)',
            ':day_end - End of the day in user\'s timezone (timezone-aware datetime)',
        ],
    }

    return render(request, 'settings/life_tracker_settings.html', context)
