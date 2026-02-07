from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import connection
from django.core.files.base import ContentFile
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import LifeTrackerColumn
from inspirations_app.models import Inspiration
from writing.models import WritingPageImage, BookCover
from PIL import Image
import io


def resize_image_with_padding(img, target_width=256, target_height=362):
    """
    Resize image to fit within target dimensions while maintaining aspect ratio.
    Adds white padding if needed to exactly match target dimensions.
    """
    # Convert to RGB first if necessary
    if img.mode in ('RGBA', 'P', 'LA'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Use thumbnail to resize maintaining aspect ratio
    img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)

    # Create a new image with white background at exact target size
    final_img = Image.new('RGB', (target_width, target_height), (255, 255, 255))

    # Calculate position to center the resized image
    x = (target_width - img.width) // 2
    y = (target_height - img.height) // 2

    # Paste the resized image onto the white background
    final_img.paste(img, (x, y))

    return final_img


def life_tracker_settings(request):
    """View for configuring Life Tracker column settings."""
    from datetime import datetime, date
    import pytz

    if request.method == 'POST':
        # Handle form submission for all columns
        columns = LifeTrackerColumn.objects.all()
        errors = []

        for column in columns:
            # Get field values for this column
            display_name = request.POST.get(f'display_name_{column.column_name}')
            tooltip_text = request.POST.get(f'tooltip_text_{column.column_name}')
            sql_query = request.POST.get(f'sql_query_{column.column_name}')
            details_display = request.POST.get(f'details_display_{column.column_name}', '')
            total_column_text = request.POST.get(f'total_column_text_{column.column_name}', '')
            start_date_str = request.POST.get(f'start_date_{column.column_name}', '').strip()
            end_date = request.POST.get(f'end_date_{column.column_name}', 'ongoing').strip() or 'ongoing'
            icon = request.POST.get(f'icon_{column.column_name}', 'bi-circle').strip() or 'bi-circle'
            parent_id = request.POST.get(f'parent_{column.column_name}', '').strip()
            new_column_name = request.POST.get(f'column_name_{column.column_name}', '').strip().lower()

            if display_name and tooltip_text and sql_query and new_column_name:
                # Check if column_name is changing and if new name already exists
                if new_column_name != column.column_name:
                    if LifeTrackerColumn.objects.filter(column_name=new_column_name).exists():
                        errors.append(f'{column.display_name}: Column name "{new_column_name}" already exists')
                        continue
                    column.column_name = new_column_name

                column.display_name = display_name
                column.tooltip_text = tooltip_text
                column.sql_query = sql_query
                column.details_display = details_display
                column.total_column_text = total_column_text

                # Handle start_date
                if start_date_str:
                    try:
                        parsed_start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                        # Validate that start_date is a Monday (weekday() == 0)
                        if parsed_start_date.weekday() != 0:
                            errors.append(f'{column.display_name}: Start date must be a Monday')
                            continue
                        column.start_date = parsed_start_date
                    except ValueError:
                        errors.append(f'{column.display_name}: Invalid start date format')
                        continue
                else:
                    column.start_date = None

                # Handle end_date
                if end_date != 'ongoing':
                    # Validate that end_date is a Sunday (weekday() == 6) if it's a date
                    try:
                        parsed_end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                        if parsed_end_date.weekday() != 6:
                            errors.append(f'{column.display_name}: End date must be a Sunday or "ongoing"')
                            continue
                    except ValueError:
                        errors.append(f'{column.display_name}: Invalid end date format (use YYYY-MM-DD or "ongoing")')
                        continue
                column.end_date = end_date

                # Handle icon
                column.icon = icon

                # Handle parent
                if parent_id:
                    try:
                        column.parent_id = int(parent_id)
                    except ValueError:
                        column.parent = None
                else:
                    column.parent = None

                # Handle UI configuration fields
                column.has_add_button = request.POST.get(f'has_add_button_{column.column_name}') == 'on'
                column.modal_type = request.POST.get(f'modal_type_{column.column_name}', '').strip()
                column.modal_title = request.POST.get(f'modal_title_{column.column_name}', '').strip()
                column.modal_body_text = request.POST.get(f'modal_body_text_{column.column_name}', '').strip()
                column.modal_input_label = request.POST.get(f'modal_input_label_{column.column_name}', '').strip()
                column.create_endpoint = request.POST.get(f'create_endpoint_{column.column_name}', '').strip()

                # Handle abandon functionality
                column.allow_abandon = request.POST.get(f'allow_abandon_{column.column_name}') == 'on'

                # Validate create_endpoint if provided
                if column.create_endpoint:
                    try:
                        from django.urls import reverse as url_reverse, NoReverseMatch
                        url_reverse(column.create_endpoint)
                    except NoReverseMatch:
                        errors.append(f'{column.display_name}: Create endpoint "{column.create_endpoint}" is not a valid URL name. Make sure the URL pattern exists and follows the format "app_name:url_name" (e.g., "fasting:log_fast")')
                        continue

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
                        elif ':day' in test_query:
                            test_query = test_query.replace(':day', '%s')
                            params.append(test_date)

                        cursor.execute(test_query, params)
                        result = cursor.fetchone()

                        if result is None or len(result) == 0:
                            raise ValueError("Query returned no results. Must return at least one row with a value.")

                        value = result[0]
                        if value is not None and not isinstance(value, (int, float, str)):
                            raise ValueError(f"Query must return a numeric or string value, got {type(value).__name__}: {value}")

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

    # Add available_fields and is_active_today to each column object
    today = date.today()
    columns_with_fields = []
    for column in columns:
        column.available_fields = available_fields.get(column.column_name, [])
        column.is_active_today = column.is_active_on(today)
        columns_with_fields.append(column)

    # Get all inspirations
    inspirations = Inspiration.objects.all()

    # Get all writing page images
    writing_images = WritingPageImage.objects.all()

    # Get or create book cover instance
    book_cover = BookCover.get_instance()

    context = {
        'columns': columns_with_fields,
        'available_parameters': [
            ':day - The current date (date object, use for comparing DATE fields)',
            ':current_date - The current date (date object, use for comparing DATE fields)',
            ':day_start - Start of the day in user\'s timezone (timezone-aware datetime)',
            ':day_end - End of the day in user\'s timezone (timezone-aware datetime)',
        ],
        'inspirations': inspirations,
        'type_choices': Inspiration.TYPE_CHOICES,
        'writing_images': writing_images,
        'book_cover': book_cover,
    }

    return render(request, 'settings/life_tracker_settings.html', context)


def add_inspiration(request):
    """Add a new inspiration."""
    if request.method == 'POST':
        uploaded_image = request.FILES.get('image')
        image_url = request.POST.get('image_url', '').strip()
        title = request.POST.get('title', '').strip()
        flip_text = request.POST.get('flip_text', '')
        type_value = request.POST.get('type')

        # Check for duplicate title
        if title and Inspiration.objects.filter(title__iexact=title).exists():
            messages.error(request, f'An inspiration with the title "{title}" already exists. Please use a different title.')
            return redirect('life_tracker_settings')

        # Check that we have either an uploaded image or image URL
        if (uploaded_image or image_url) and title and type_value:
            try:
                # Process image from upload or URL
                if uploaded_image:
                    img = Image.open(uploaded_image)
                    filename = uploaded_image.name
                elif image_url:
                    import requests
                    response = requests.get(image_url, timeout=10)
                    response.raise_for_status()
                    img = Image.open(io.BytesIO(response.content))
                    # Generate filename from URL
                    filename = image_url.split('/')[-1].split('?')[0] or 'image.jpg'
                    if not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        filename += '.jpg'

                # Resize image to 256x362 maintaining aspect ratio with padding
                img = resize_image_with_padding(img, 256, 362)

                # Save to BytesIO
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85)
                output.seek(0)

                # Create ContentFile with resized image
                resized_image = ContentFile(output.read(), name=filename)

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
            except Exception as e:
                messages.error(request, f'Error processing image: {str(e)}')
        else:
            messages.error(request, 'Please fill in all required fields (Image or Image URL, Title, and Type).')

    return redirect(reverse('life_tracker_settings') + '#inspirationsSection')


def edit_inspiration(request, inspiration_id):
    """Edit an existing inspiration."""
    inspiration = get_object_or_404(Inspiration, id=inspiration_id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        flip_text = request.POST.get('flip_text', '')
        type_value = request.POST.get('type')
        url = request.POST.get('url', '').strip() or None
        uploaded_image = request.FILES.get('image')
        image_url = request.POST.get('image_url', '').strip()

        # Check for duplicate title (excluding current inspiration)
        if title and Inspiration.objects.filter(title__iexact=title).exclude(id=inspiration_id).exists():
            messages.error(request, f'An inspiration with the title "{title}" already exists. Please use a different title.')
            return redirect(reverse('life_tracker_settings') + '#inspirationsSection')

        if title and type_value:
            inspiration.title = title
            inspiration.flip_text = flip_text
            inspiration.type = type_value
            inspiration.url = url

            # Handle image upload or URL if provided
            if uploaded_image or image_url:
                try:
                    # Process image from upload or URL
                    if uploaded_image:
                        img = Image.open(uploaded_image)
                        filename = uploaded_image.name
                    elif image_url:
                        import requests
                        response = requests.get(image_url, timeout=10)
                        response.raise_for_status()
                        img = Image.open(io.BytesIO(response.content))
                        # Generate filename from URL
                        filename = image_url.split('/')[-1].split('?')[0] or 'image.jpg'
                        if not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                            filename += '.jpg'

                    # Resize image to 256x362 maintaining aspect ratio with padding
                    img = resize_image_with_padding(img, 256, 362)

                    # Save to BytesIO
                    output = io.BytesIO()
                    img.save(output, format='JPEG', quality=85)
                    output.seek(0)

                    # Create ContentFile with resized image
                    resized_image = ContentFile(output.read(), name=filename)
                    inspiration.image = resized_image
                except Exception as e:
                    messages.error(request, f'Error processing image: {str(e)}')
                    return redirect(reverse('life_tracker_settings') + '#inspirationsSection')

            inspiration.save()
            messages.success(request, 'Inspiration updated successfully!')
        else:
            messages.error(request, 'Title and Type are required.')

    return redirect(reverse('life_tracker_settings') + f'#inspiration-{inspiration_id}')


def delete_inspiration(request, inspiration_id):
    """Delete an inspiration."""
    inspiration = get_object_or_404(Inspiration, id=inspiration_id)

    if request.method == 'POST':
        inspiration.delete()
        messages.success(request, 'Inspiration deleted successfully!')

    return redirect(reverse('life_tracker_settings') + '#inspirationsSection')


def add_writing_image(request):
    """Add a new writing page image."""
    if request.method == 'POST':
        image = request.FILES.get('image')
        excerpt = request.POST.get('excerpt', '').strip()

        if image and excerpt:
            WritingPageImage.objects.create(
                image=image,
                excerpt=excerpt,
                enabled=True
            )
            messages.success(request, 'Writing page image added successfully!')
        else:
            messages.error(request, 'Please fill in all required fields (Image and Excerpt).')

    return redirect('life_tracker_settings')


def edit_writing_image(request, image_id):
    """Edit an existing writing page image."""
    writing_image = get_object_or_404(WritingPageImage, id=image_id)

    if request.method == 'POST':
        excerpt = request.POST.get('excerpt', '').strip()
        enabled = request.POST.get('enabled') == 'on'

        if excerpt:
            writing_image.excerpt = excerpt
            writing_image.enabled = enabled

            # Handle new image upload
            new_image = request.FILES.get('image')
            if new_image:
                writing_image.image = new_image

            writing_image.save()
            messages.success(request, 'Writing page image updated successfully!')
        else:
            messages.error(request, 'Excerpt is required.')

    return redirect('life_tracker_settings')


def delete_writing_image(request, image_id):
    """Delete a writing page image."""
    writing_image = get_object_or_404(WritingPageImage, id=image_id)

    if request.method == 'POST':
        writing_image.delete()
        messages.success(request, 'Writing page image deleted successfully!')

    return redirect('life_tracker_settings')


def upload_book_cover(request):
    """Upload or update the book cover image."""
    if request.method == 'POST':
        image = request.FILES.get('image')

        if image:
            book_cover = BookCover.get_instance()
            book_cover.image = image
            book_cover.save()
            messages.success(request, 'Book cover uploaded successfully!')
        else:
            messages.error(request, 'Please select an image file.')

    return redirect('life_tracker_settings')


def add_habit(request):
    """Add a new habit (Life Tracker Column)."""
    from datetime import datetime, date

    if request.method == 'POST':
        column_name = request.POST.get('column_name', '').strip().lower()
        display_name = request.POST.get('display_name', '').strip()
        tooltip_text = request.POST.get('tooltip_text', '').strip()
        sql_query = request.POST.get('sql_query', '').strip()
        details_display = request.POST.get('details_display', '').strip()
        total_column_text = request.POST.get('total_column_text', '').strip()
        start_date_str = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', 'ongoing').strip() or 'ongoing'
        icon = request.POST.get('icon', 'bi-circle').strip() or 'bi-circle'
        parent_id = request.POST.get('parent', '').strip()

        # Get UI configuration fields
        has_add_button = request.POST.get('has_add_button') == 'on'
        modal_type = request.POST.get('modal_type', '').strip()
        modal_title = request.POST.get('modal_title', '').strip()
        modal_body_text = request.POST.get('modal_body_text', '').strip()
        modal_input_label = request.POST.get('modal_input_label', '').strip()
        create_endpoint = request.POST.get('create_endpoint', '').strip()
        allow_abandon = request.POST.get('allow_abandon') == 'on'

        # Check if column_name already exists
        if column_name and LifeTrackerColumn.objects.filter(column_name=column_name).exists():
            messages.error(request, f'A habit with column name "{column_name}" already exists.')
            return redirect(reverse('life_tracker_settings') + '#lifeTrackerSection')

        if column_name and display_name and tooltip_text and sql_query:
            try:
                # Parse start_date if provided, otherwise use today
                if start_date_str:
                    try:
                        habit_start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                        # Validate that start_date is a Monday (weekday() == 0)
                        if habit_start_date.weekday() != 0:
                            messages.error(request, 'Start date must be a Monday.')
                            return redirect(reverse('life_tracker_settings') + '#lifeTrackerSection')
                    except ValueError:
                        messages.error(request, 'Invalid start date format. Use YYYY-MM-DD.')
                        return redirect(reverse('life_tracker_settings') + '#lifeTrackerSection')
                else:
                    habit_start_date = date.today()

                # Validate end_date if it's not "ongoing"
                if end_date != 'ongoing':
                    try:
                        parsed_end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                        # Validate that end_date is a Sunday (weekday() == 6)
                        if parsed_end_date.weekday() != 6:
                            messages.error(request, 'End date must be a Sunday or "ongoing".')
                            return redirect(reverse('life_tracker_settings') + '#lifeTrackerSection')
                    except ValueError:
                        messages.error(request, 'Invalid end date format. Use YYYY-MM-DD or "ongoing".')
                        return redirect(reverse('life_tracker_settings') + '#lifeTrackerSection')

                # Handle parent
                parent_habit = None
                if parent_id:
                    try:
                        parent_habit = LifeTrackerColumn.objects.get(id=int(parent_id))
                    except (ValueError, LifeTrackerColumn.DoesNotExist):
                        parent_habit = None

                # Validate create_endpoint if provided
                if create_endpoint:
                    try:
                        from django.urls import reverse as url_reverse, NoReverseMatch
                        url_reverse(create_endpoint)
                    except NoReverseMatch:
                        messages.error(request, f'Create endpoint "{create_endpoint}" is not a valid URL name. Make sure the URL pattern exists and follows the format "app_name:url_name" (e.g., "fasting:log_fast")')
                        return redirect(reverse('life_tracker_settings') + '#lifeTrackerSection')

                # Validate SQL query
                try:
                    from django.db import connection
                    import pytz

                    user_tz = pytz.timezone('America/Los_Angeles')
                    test_date = date(2024, 1, 1)
                    day_start = user_tz.localize(datetime.combine(test_date, datetime.min.time()))
                    day_end = user_tz.localize(datetime.combine(test_date, datetime.max.time()))

                    with connection.cursor() as cursor:
                        test_query = sql_query
                        params = []

                        if ':current_date' in test_query:
                            test_query = test_query.replace(':current_date', '%s')
                            params.append(test_date)
                        elif ':day_start' in test_query or ':day_end' in test_query:
                            test_query = test_query.replace(':day_start', '%s').replace(':day_end', '%s')
                            params.extend([day_start, day_end])
                        elif ':day' in test_query:
                            test_query = test_query.replace(':day', '%s')
                            params.append(test_date)

                        cursor.execute(test_query, params)
                        result = cursor.fetchone()

                        if result is None or len(result) == 0:
                            raise ValueError("Query returned no results. Must return at least one row with a value.")

                        value = result[0]
                        if value is not None and not isinstance(value, (int, float)) and not isinstance(value, str):
                            raise ValueError(f"Query must return a numeric or string value, got {type(value).__name__}: {value}")

                except Exception as e:
                    messages.error(request, f'SQL Query Error: {str(e)}')
                    return redirect(reverse('life_tracker_settings') + '#lifeTrackerSection')

                LifeTrackerColumn.objects.create(
                    column_name=column_name,
                    display_name=display_name,
                    tooltip_text=tooltip_text,
                    sql_query=sql_query,
                    details_display=details_display,
                    total_column_text=total_column_text,
                    start_date=habit_start_date,
                    end_date=end_date,
                    icon=icon,
                    parent=parent_habit,
                    has_add_button=has_add_button,
                    modal_type=modal_type,
                    modal_title=modal_title,
                    modal_body_text=modal_body_text,
                    modal_input_label=modal_input_label,
                    create_endpoint=create_endpoint,
                    allow_abandon=allow_abandon
                )
                messages.success(request, f'Habit "{display_name}" added successfully!')
            except Exception as e:
                messages.error(request, f'Error adding habit: {str(e)}')
        else:
            messages.error(request, 'Please fill in all required fields.')

    return redirect(reverse('life_tracker_settings') + '#lifeTrackerSection')



@require_POST
def import_outlook_calendar(request):
    """Import calendar events from an Outlook JSON export."""
    import json
    from calendar_events.views import import_calendar_events

    file = request.FILES.get('file')

    if not file:
        messages.error(request, 'Please select a JSON file to upload.')
        return redirect(reverse('life_tracker_settings') + '#dataImportsSection')

    if not file.name.endswith('.json'):
        messages.error(request, 'Please upload a JSON file.')
        return redirect(reverse('life_tracker_settings') + '#dataImportsSection')

    try:
        # Parse JSON file
        content = file.read().decode('utf-8')
        data = json.loads(content)

        # Use shared import function
        created_count, updated_count = import_calendar_events(data)

        messages.success(
            request,
            f'Import complete: {created_count} events created, {updated_count} events updated.'
        )

    except json.JSONDecodeError as e:
        messages.error(request, f'Invalid JSON file: {str(e)}')
    except Exception as e:
        messages.error(request, f'Error importing calendar: {str(e)}')

    return redirect(reverse('life_tracker_settings') + '#dataImportsSection')


@require_POST
def toggle_abandon_day(request, column_name):
    """Toggle the abandoned status for a specific day for a given column."""
    import json

    column = get_object_or_404(LifeTrackerColumn, column_name=column_name)

    # Get the date from the request
    try:
        data = json.loads(request.body)
        date_str = data.get("date")  # Expected format: YYYY-MM-DD

        if not date_str:
            return JsonResponse({"success": False, "error": "Date is required"}, status=400)

        # Get or initialize the abandoned_status dict
        abandoned_status = column.abandoned_status or {}

        # Toggle the abandoned status
        if date_str in abandoned_status and abandoned_status[date_str]:
            # Currently abandoned, so un-abandon it
            abandoned_status[date_str] = False
            is_abandoned = False
        else:
            # Not abandoned, so abandon it
            abandoned_status[date_str] = True
            is_abandoned = True

        # Save the updated status
        column.abandoned_status = abandoned_status
        column.save()

        return JsonResponse({
            "success": True,
            "is_abandoned": is_abandoned,
            "date": date_str
        })

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

