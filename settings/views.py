from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import connection
from django.core.files.base import ContentFile
from .models import LifeTrackerColumn
from inspirations_app.models import Inspiration
from inspirations_app.utils import get_youtube_trailer_url
from PIL import Image
import io


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
            details_display = request.POST.get(f'details_display_{column.column_name}', '')
            order = request.POST.get(f'order_{column.column_name}')
            enabled = request.POST.get(f'enabled_{column.column_name}') == 'on'

            if display_name and tooltip_text and sql_query and order:
                column.display_name = display_name
                column.tooltip_text = tooltip_text
                column.sql_query = sql_query
                column.details_display = details_display
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

    # Define available fields for each column type
    available_fields = {
        'run': ['start', 'end', 'sport_id', 'average_heart_rate', 'max_heart_rate', 'calories_burned', 'distance_in_miles'],
        'strength': ['start', 'end', 'sport_id', 'average_heart_rate', 'max_heart_rate', 'calories_burned'],
        'fast': ['duration', 'fast_end_date'],
        'write': ['log_date', 'duration'],
        'weigh_in': ['measurement_time', 'weight'],
        'eat_clean': ['consumption_date', 'calories', 'fat', 'carbs', 'protein'],
    }

    # Add available_fields to each column object
    columns_with_fields = []
    for column in columns:
        column.available_fields = available_fields.get(column.column_name, [])
        columns_with_fields.append(column)

    # Get all inspirations
    inspirations = Inspiration.objects.all()

    context = {
        'columns': columns_with_fields,
        'available_parameters': [
            ':current_date - The current date (date object, use for comparing DATE fields)',
            ':day_start - Start of the day in user\'s timezone (timezone-aware datetime)',
            ':day_end - End of the day in user\'s timezone (timezone-aware datetime)',
        ],
        'inspirations': inspirations,
        'type_choices': Inspiration.TYPE_CHOICES,
    }

    return render(request, 'settings/life_tracker_settings.html', context)


def add_inspiration(request):
    """Add a new inspiration."""
    if request.method == 'POST':
        image = request.FILES.get('image')
        title = request.POST.get('title', '').strip()
        flip_text = request.POST.get('flip_text', '')
        type_value = request.POST.get('type')

        if image and title and type_value:
            # Resize image to 256x362
            img = Image.open(image)
            img = img.resize((256, 362), Image.Resampling.LANCZOS)

            # Convert to RGB if necessary (handles RGBA, P mode, etc.)
            if img.mode in ('RGBA', 'P', 'LA'):
                # Create white background for transparent images
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Save to BytesIO
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85)
            output.seek(0)

            # Create ContentFile with resized image
            resized_image = ContentFile(output.read(), name=image.name)

            # Get URL from form
            url = request.POST.get('url', '').strip() or None

            Inspiration.objects.create(
                image=resized_image,
                title=title,
                flip_text=flip_text,
                type=type_value,
                url=url
            )
            messages.success(request, 'Inspiration added successfully!')
        else:
            messages.error(request, 'Please fill in all required fields (Image, Title, and Type).')

    return redirect('life_tracker_settings')


def edit_inspiration(request, inspiration_id):
    """Edit an existing inspiration."""
    inspiration = get_object_or_404(Inspiration, id=inspiration_id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        flip_text = request.POST.get('flip_text', '')
        type_value = request.POST.get('type')
        url = request.POST.get('url', '').strip() or None

        if title and type_value:
            inspiration.title = title
            inspiration.flip_text = flip_text
            inspiration.type = type_value
            inspiration.url = url
            inspiration.save()
            messages.success(request, 'Inspiration updated successfully!')
        else:
            messages.error(request, 'Title and Type are required.')

    return redirect('life_tracker_settings')


def delete_inspiration(request, inspiration_id):
    """Delete an inspiration."""
    inspiration = get_object_or_404(Inspiration, id=inspiration_id)

    if request.method == 'POST':
        inspiration.delete()
        messages.success(request, 'Inspiration deleted successfully!')

    return redirect('life_tracker_settings')
