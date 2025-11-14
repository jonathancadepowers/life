from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import connection
from .models import LifeTrackerColumn


def life_tracker_settings(request):
    """View for configuring Life Tracker column settings."""
    if request.method == 'POST':
        # Handle form submission for all columns
        from datetime import datetime, date
        import pytz

        columns = LifeTrackerColumn.objects.all()
        errors = []

        for column in columns:
            # Get field values for this column
            display_name = request.POST.get(f'display_name_{column.column_name}')
            tooltip_text = request.POST.get(f'tooltip_text_{column.column_name}')
            sql_query = request.POST.get(f'sql_query_{column.column_name}')
            order = request.POST.get(f'order_{column.column_name}')
            enabled = request.POST.get(f'enabled_{column.column_name}') == 'on'

            if display_name and tooltip_text and sql_query and order:
                column.display_name = display_name
                column.tooltip_text = tooltip_text
                column.sql_query = sql_query
                column.order = int(order)
                column.enabled = enabled

                # Validate SQL query
                try:
                    user_tz = pytz.timezone('America/Los_Angeles')
                    test_date = date(2024, 1, 1)
                    day_start = user_tz.localize(datetime.combine(test_date, datetime.min.time()))
                    day_end = user_tz.localize(datetime.combine(test_date, datetime.max.time()))

                    with connection.cursor() as cursor:
                        test_query = column.sql_query
                        params = []

                        if ':current_date' in test_query:
                            test_query = test_query.replace(':current_date', '%s')
                            params.append(test_date)
                        elif ':day_start' in test_query or ':day_end' in test_query:
                            test_query = test_query.replace(':day_start', '%s').replace(':day_end', '%s')
                            params.extend([day_start, day_end])

                        cursor.execute(test_query, params)
                        result = cursor.fetchone()

                        if result is None:
                            raise ValueError("Query returned no results. Must return at least one row with a numeric value.")

                        value = result[0]
                        if value is not None and not isinstance(value, (int, float)):
                            raise ValueError(f"Query must return a numeric value, got {type(value).__name__}: {value}")

                    column.save()
                except Exception as e:
                    errors.append(f'{column.display_name}: {str(e)}')

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            messages.success(request, 'Successfully updated all column settings.')

        return redirect('life_tracker_settings')

    # Get all columns ordered
    columns = LifeTrackerColumn.objects.all()

    context = {
        'columns': columns,
        'available_parameters': [
            ':current_date - The current date (date object, use for comparing DATE fields)',
            ':day_start - Start of the day in user\'s timezone (timezone-aware datetime)',
            ':day_end - End of the day in user\'s timezone (timezone-aware datetime)',
        ],
    }

    return render(request, 'settings/life_tracker_settings.html', context)
