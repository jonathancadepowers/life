from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import connection
from django.core.files.base import ContentFile
from django.urls import reverse
from .models import LifeTrackerColumn
from inspirations_app.models import Inspiration
from inspirations_app.utils import get_youtube_trailer_url
from writing.models import WritingPageImage, BookCover
from PIL import Image, ImageOps
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
            order = request.POST.get(f'order_{column.column_name}')
            enabled = request.POST.get(f'enabled_{column.column_name}') == 'on'
            start_date_str = request.POST.get(f'start_date_{column.column_name}', '').strip()
            end_date = request.POST.get(f'end_date_{column.column_name}', 'ongoing').strip() or 'ongoing'

            if display_name and tooltip_text and sql_query and order:
                column.display_name = display_name
                column.tooltip_text = tooltip_text
                column.sql_query = sql_query
                column.details_display = details_display
                column.order = int(order)
                column.enabled = enabled

                # Handle start_date
                if start_date_str:
                    try:
                        column.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        errors.append(f'{column.display_name}: Invalid start date format')
                        continue
                else:
                    column.start_date = None

                # Handle end_date
                column.end_date = end_date

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

        # Validate that exactly 6 habits are active today
        if not errors:
            today = date.today()
            active_count = sum(1 for col in columns if col.is_active_on(today))

            if active_count != 6:
                errors.append(f'You must have exactly 6 active habits as of today. Currently you have {active_count} active habit(s).')

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
    from datetime import date

    if request.method == 'POST':
        column_name = request.POST.get('column_name', '').strip().lower()
        display_name = request.POST.get('display_name', '').strip()
        tooltip_text = request.POST.get('tooltip_text', '').strip()
        sql_query = request.POST.get('sql_query', '').strip()
        details_display = request.POST.get('details_display', '').strip()
        order = request.POST.get('order', '0')

        # Check if column_name already exists
        if column_name and LifeTrackerColumn.objects.filter(column_name=column_name).exists():
            messages.error(request, f'A habit with column name "{column_name}" already exists.')
            return redirect(reverse('life_tracker_settings') + '#lifeTrackerSection')

        if column_name and display_name and tooltip_text and sql_query:
            try:
                LifeTrackerColumn.objects.create(
                    column_name=column_name,
                    display_name=display_name,
                    tooltip_text=tooltip_text,
                    sql_query=sql_query,
                    details_display=details_display,
                    order=int(order),
                    enabled=True,
                    start_date=date.today(),
                    end_date='ongoing'
                )
                messages.success(request, f'Habit "{display_name}" added successfully!')
            except Exception as e:
                messages.error(request, f'Error adding habit: {str(e)}')
        else:
            messages.error(request, 'Please fill in all required fields.')

    return redirect(reverse('life_tracker_settings') + '#lifeTrackerSection')
