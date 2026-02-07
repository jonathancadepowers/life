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

_ANCHOR_LIFE_TRACKER = '#lifeTrackerSection'
_ANCHOR_INSPIRATIONS = '#inspirationsSection'
_ANCHOR_DATA_IMPORTS = '#dataImportsSection'
_TMPL_CURRENT_DATE = ':current_date'
_TMPL_DAY_END = ':day_end'
_TMPL_DAY_START = ':day_start'


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


def _validate_sql_query(sql_query):
    """
    Validate a Life Tracker column SQL query by executing it with test parameters.
    Raises ValueError or other exceptions on validation failure.
    """
    from datetime import datetime, date
    import pytz

    user_tz = pytz.timezone('America/Los_Angeles')
    test_date = date(2024, 1, 1)
    day_start = user_tz.localize(datetime.combine(test_date, datetime.min.time()))
    day_end = user_tz.localize(datetime.combine(test_date, datetime.max.time()))

    with connection.cursor() as cursor:
        test_query = sql_query
        params = []

        if _TMPL_CURRENT_DATE in test_query:
            test_query = test_query.replace(_TMPL_CURRENT_DATE, '%s')
            params.append(test_date)
        elif _TMPL_DAY_START in test_query or _TMPL_DAY_END in test_query:
            test_query = test_query.replace(_TMPL_DAY_START, '%s').replace(_TMPL_DAY_END, '%s')
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


def _validate_create_endpoint(endpoint):
    """
    Validate that a create_endpoint is a resolvable URL name.
    Returns an error message string on failure, or None on success.
    """
    if not endpoint:
        return None
    try:
        from django.urls import reverse as url_reverse, NoReverseMatch
        url_reverse(endpoint)
        return None
    except NoReverseMatch:
        return (
            f'Create endpoint "{endpoint}" is not a valid URL name. '
            'Make sure the URL pattern exists and follows the format "app_name:url_name" '
            '(e.g., "fasting:log_fast")'
        )


def _parse_and_validate_start_date(start_date_str):
    """
    Parse a start date string and validate it is a Monday.
    Returns (parsed_date, error_message). error_message is None on success.
    """
    from datetime import datetime

    if not start_date_str:
        return None, None
    try:
        parsed = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if parsed.weekday() != 0:
            return None, 'Start date must be a Monday'
        return parsed, None
    except ValueError:
        return None, 'Invalid start date format'


def _parse_and_validate_end_date(end_date_str):
    """
    Parse an end date string and validate it is a Sunday or 'ongoing'.
    Returns error_message or None on success.
    """
    from datetime import datetime

    if end_date_str == 'ongoing':
        return None
    try:
        parsed = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        if parsed.weekday() != 6:
            return 'End date must be a Sunday or "ongoing"'
        return None
    except ValueError:
        return 'Invalid end date format (use YYYY-MM-DD or "ongoing")'


def _extract_column_fields(request_post, col_name):
    """Extract all POST field values for a single column by its column_name prefix."""
    return {
        'display_name': request_post.get(f'display_name_{col_name}'),
        'tooltip_text': request_post.get(f'tooltip_text_{col_name}'),
        'sql_query': request_post.get(f'sql_query_{col_name}'),
        'details_display': request_post.get(f'details_display_{col_name}', ''),
        'total_column_text': request_post.get(f'total_column_text_{col_name}', ''),
        'start_date_str': request_post.get(f'start_date_{col_name}', '').strip(),
        'end_date': request_post.get(f'end_date_{col_name}', 'ongoing').strip() or 'ongoing',
        'icon': request_post.get(f'icon_{col_name}', 'bi-circle').strip() or 'bi-circle',
        'parent_id': request_post.get(f'parent_{col_name}', '').strip(),
        'new_column_name': request_post.get(f'column_name_{col_name}', '').strip().lower(),
        'has_add_button': request_post.get(f'has_add_button_{col_name}') == 'on',
        'modal_type': request_post.get(f'modal_type_{col_name}', '').strip(),
        'modal_title': request_post.get(f'modal_title_{col_name}', '').strip(),
        'modal_body_text': request_post.get(f'modal_body_text_{col_name}', '').strip(),
        'modal_input_label': request_post.get(f'modal_input_label_{col_name}', '').strip(),
        'create_endpoint': request_post.get(f'create_endpoint_{col_name}', '').strip(),
        'allow_abandon': request_post.get(f'allow_abandon_{col_name}') == 'on',
    }


def _update_single_column(column, fields, errors):
    """
    Apply validated field values to a column and save. Appends to errors list on failure.
    Returns True if the column should be skipped (due to validation error), False otherwise.
    """
    f = fields
    display_label = column.display_name

    if not all([f['display_name'], f['tooltip_text'], f['sql_query'], f['new_column_name']]):
        return True  # skip: missing required fields

    # Rename column_name if changed
    if f['new_column_name'] != column.column_name:
        if LifeTrackerColumn.objects.filter(column_name=f['new_column_name']).exists():
            errors.append(f'{display_label}: Column name "{f["new_column_name"]}" already exists')
            return True
        column.column_name = f['new_column_name']

    column.display_name = f['display_name']
    column.tooltip_text = f['tooltip_text']
    column.sql_query = f['sql_query']
    column.details_display = f['details_display']
    column.total_column_text = f['total_column_text']
    column.icon = f['icon']

    # Start date
    parsed_start, start_err = _parse_and_validate_start_date(f['start_date_str'])
    if start_err:
        errors.append(f'{display_label}: {start_err}')
        return True
    column.start_date = parsed_start

    # End date
    end_err = _parse_and_validate_end_date(f['end_date'])
    if end_err:
        errors.append(f'{display_label}: {end_err}')
        return True
    column.end_date = f['end_date']

    # Parent
    if f['parent_id']:
        try:
            column.parent_id = int(f['parent_id'])
        except ValueError:
            column.parent = None
    else:
        column.parent = None

    # UI configuration
    column.has_add_button = f['has_add_button']
    column.modal_type = f['modal_type']
    column.modal_title = f['modal_title']
    column.modal_body_text = f['modal_body_text']
    column.modal_input_label = f['modal_input_label']
    column.create_endpoint = f['create_endpoint']
    column.allow_abandon = f['allow_abandon']

    # Validate create_endpoint
    endpoint_err = _validate_create_endpoint(column.create_endpoint)
    if endpoint_err:
        errors.append(f'{display_label}: {endpoint_err}')
        return True

    # Validate SQL query and save
    try:
        _validate_sql_query(column.sql_query)
        column.save()
    except Exception as e:
        errors.append(f'{display_label}: {str(e)}')

    return False


def _handle_settings_post(request):
    """Process the POST for life_tracker_settings, returning any errors."""
    columns = LifeTrackerColumn.objects.all()
    errors = []

    for column in columns:
        fields = _extract_column_fields(request.POST, column.column_name)
        _update_single_column(column, fields, errors)

    return errors


def life_tracker_settings(request):
    """View for configuring Life Tracker column settings."""
    from datetime import date

    if request.method == 'POST':
        errors = _handle_settings_post(request)

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            messages.success(request, 'Successfully updated all column settings.')

        return redirect('life_tracker_settings')

    # GET: Render settings page
    columns = LifeTrackerColumn.objects.all()

    available_fields = {
        'run': ['start', 'end', 'sport_id', 'average_heart_rate', 'max_heart_rate', 'calories_burned', 'distance_in_miles'],
        'strength': ['start', 'end', 'sport_id', 'average_heart_rate', 'max_heart_rate', 'calories_burned'],
        'fast': ['duration', 'fast_end_date'],
        'write': ['log_date', 'duration'],
        'weigh_in': ['measurement_time', 'weight'],
        'eat_clean': ['consumption_date', 'calories', 'fat', 'carbs', 'protein'],
    }

    today = date.today()
    columns_with_fields = []
    for column in columns:
        column.available_fields = available_fields.get(column.column_name, [])
        column.is_active_today = column.is_active_on(today)
        columns_with_fields.append(column)

    context = {
        'columns': columns_with_fields,
        'available_parameters': [
            ':day - The current date (date object, use for comparing DATE fields)',
            ':current_date - The current date (date object, use for comparing DATE fields)',
            ':day_start - Start of the day in user\'s timezone (timezone-aware datetime)',
            ':day_end - End of the day in user\'s timezone (timezone-aware datetime)',
        ],
        'inspirations': Inspiration.objects.all(),
        'type_choices': Inspiration.TYPE_CHOICES,
        'writing_images': WritingPageImage.objects.all(),
        'book_cover': BookCover.get_instance(),
    }

    return render(request, 'settings/life_tracker_settings.html', context)


def _load_image_from_source(uploaded_image, image_url):
    """
    Load an image and filename from either an uploaded file or a URL.
    Returns (PIL.Image, filename) or raises an exception on failure.
    """
    if uploaded_image:
        return Image.open(uploaded_image), uploaded_image.name

    import requests
    response = requests.get(image_url, timeout=10)
    response.raise_for_status()
    img = Image.open(io.BytesIO(response.content))
    filename = image_url.split('/')[-1].split('?')[0] or 'image.jpg'
    valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
    if not filename.lower().endswith(valid_extensions):
        filename += '.jpg'
    return img, filename


def _process_inspiration_image(uploaded_image, image_url):
    """
    Load, resize, and return a ContentFile for an inspiration image.
    Returns the resized ContentFile, or raises an exception on failure.
    """
    img, filename = _load_image_from_source(uploaded_image, image_url)
    img = resize_image_with_padding(img, 256, 362)
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=85)
    output.seek(0)
    return ContentFile(output.read(), name=filename)


def add_inspiration(request):
    """Add a new inspiration."""
    if request.method != 'POST':
        return redirect(reverse('life_tracker_settings') + _ANCHOR_INSPIRATIONS)

    uploaded_image = request.FILES.get('image')
    image_url = request.POST.get('image_url', '').strip()
    title = request.POST.get('title', '').strip()
    flip_text = request.POST.get('flip_text', '')
    type_value = request.POST.get('type')

    if not ((uploaded_image or image_url) and title and type_value):
        messages.error(request, 'Please fill in all required fields (Image or Image URL, Title, and Type).')
        return redirect(reverse('life_tracker_settings') + _ANCHOR_INSPIRATIONS)

    if Inspiration.objects.filter(title__iexact=title).exists():
        messages.error(request, f'An inspiration with the title "{title}" already exists. Please use a different title.')
        return redirect(reverse('life_tracker_settings') + _ANCHOR_INSPIRATIONS)

    try:
        resized_image = _process_inspiration_image(uploaded_image, image_url)
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

    return redirect(reverse('life_tracker_settings') + _ANCHOR_INSPIRATIONS)


def edit_inspiration(request, inspiration_id):
    """Edit an existing inspiration."""
    inspiration = get_object_or_404(Inspiration, id=inspiration_id)
    redirect_url = reverse('life_tracker_settings') + f'#inspiration-{inspiration_id}'

    if request.method != 'POST':
        return redirect(redirect_url)

    title = request.POST.get('title', '').strip()
    type_value = request.POST.get('type')

    if not (title and type_value):
        messages.error(request, 'Title and Type are required.')
        return redirect(redirect_url)

    if Inspiration.objects.filter(title__iexact=title).exclude(id=inspiration_id).exists():
        messages.error(request, f'An inspiration with the title "{title}" already exists. Please use a different title.')
        return redirect(reverse('life_tracker_settings') + _ANCHOR_INSPIRATIONS)

    inspiration.title = title
    inspiration.flip_text = request.POST.get('flip_text', '')
    inspiration.type = type_value
    inspiration.url = request.POST.get('url', '').strip() or None

    uploaded_image = request.FILES.get('image')
    image_url = request.POST.get('image_url', '').strip()

    if uploaded_image or image_url:
        try:
            inspiration.image = _process_inspiration_image(uploaded_image, image_url)
        except Exception as e:
            messages.error(request, f'Error processing image: {str(e)}')
            return redirect(reverse('life_tracker_settings') + _ANCHOR_INSPIRATIONS)

    inspiration.save()
    messages.success(request, 'Inspiration updated successfully!')

    return redirect(redirect_url)


def delete_inspiration(request, inspiration_id):
    """Delete an inspiration."""
    inspiration = get_object_or_404(Inspiration, id=inspiration_id)

    if request.method == 'POST':
        inspiration.delete()
        messages.success(request, 'Inspiration deleted successfully!')

    return redirect(reverse('life_tracker_settings') + _ANCHOR_INSPIRATIONS)


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


def _redirect_life_tracker():
    """Shortcut redirect back to the life tracker settings section."""
    return redirect(reverse('life_tracker_settings') + _ANCHOR_LIFE_TRACKER)


def _resolve_parent_habit(parent_id_str):
    """Resolve a parent habit from a string ID. Returns the parent column or None."""
    if not parent_id_str:
        return None
    try:
        return LifeTrackerColumn.objects.get(id=int(parent_id_str))
    except (ValueError, LifeTrackerColumn.DoesNotExist):
        return None


def _validate_habit_dates(post_data):
    """
    Parse and validate start_date and end_date from POST data.
    Returns (start_date, end_date_str, error_message).
    error_message is None on success.
    """
    from datetime import date

    start_date_str = post_data.get('start_date', '').strip()
    habit_start_date, start_err = _parse_and_validate_start_date(start_date_str)
    if start_err:
        return None, None, f'{start_err}.'
    if habit_start_date is None:
        habit_start_date = date.today()

    end_date = post_data.get('end_date', 'ongoing').strip() or 'ongoing'
    end_err = _parse_and_validate_end_date(end_date)
    if end_err:
        return None, None, f'{end_err}.'

    return habit_start_date, end_date, None


def add_habit(request):
    """Add a new habit (Life Tracker Column)."""
    if request.method != 'POST':
        return _redirect_life_tracker()

    column_name = request.POST.get('column_name', '').strip().lower()
    display_name = request.POST.get('display_name', '').strip()
    tooltip_text = request.POST.get('tooltip_text', '').strip()
    sql_query = request.POST.get('sql_query', '').strip()

    if not all([column_name, display_name, tooltip_text, sql_query]):
        messages.error(request, 'Please fill in all required fields.')
        return _redirect_life_tracker()

    if LifeTrackerColumn.objects.filter(column_name=column_name).exists():
        messages.error(request, f'A habit with column name "{column_name}" already exists.')
        return _redirect_life_tracker()

    habit_start_date, end_date, date_err = _validate_habit_dates(request.POST)
    if date_err:
        messages.error(request, date_err)
        return _redirect_life_tracker()

    create_endpoint = request.POST.get('create_endpoint', '').strip()
    endpoint_err = _validate_create_endpoint(create_endpoint)
    if endpoint_err:
        messages.error(request, endpoint_err)
        return _redirect_life_tracker()

    try:
        _validate_sql_query(sql_query)
    except Exception as e:
        messages.error(request, f'SQL Query Error: {str(e)}')
        return _redirect_life_tracker()

    try:
        LifeTrackerColumn.objects.create(
            column_name=column_name,
            display_name=display_name,
            tooltip_text=tooltip_text,
            sql_query=sql_query,
            details_display=request.POST.get('details_display', '').strip(),
            total_column_text=request.POST.get('total_column_text', '').strip(),
            start_date=habit_start_date,
            end_date=end_date,
            icon=request.POST.get('icon', 'bi-circle').strip() or 'bi-circle',
            parent=_resolve_parent_habit(request.POST.get('parent', '').strip()),
            has_add_button=request.POST.get('has_add_button') == 'on',
            modal_type=request.POST.get('modal_type', '').strip(),
            modal_title=request.POST.get('modal_title', '').strip(),
            modal_body_text=request.POST.get('modal_body_text', '').strip(),
            modal_input_label=request.POST.get('modal_input_label', '').strip(),
            create_endpoint=create_endpoint,
            allow_abandon=request.POST.get('allow_abandon') == 'on',
        )
        messages.success(request, f'Habit "{display_name}" added successfully!')
    except Exception as e:
        messages.error(request, f'Error adding habit: {str(e)}')

    return _redirect_life_tracker()



@require_POST
def import_outlook_calendar(request):
    """Import calendar events from an Outlook JSON export."""
    import json
    from calendar_events.views import import_calendar_events

    file = request.FILES.get('file')

    if not file:
        messages.error(request, 'Please select a JSON file to upload.')
        return redirect(reverse('life_tracker_settings') + _ANCHOR_DATA_IMPORTS)

    if not file.name.endswith('.json'):
        messages.error(request, 'Please upload a JSON file.')
        return redirect(reverse('life_tracker_settings') + _ANCHOR_DATA_IMPORTS)

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

    return redirect(reverse('life_tracker_settings') + _ANCHOR_DATA_IMPORTS)


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

