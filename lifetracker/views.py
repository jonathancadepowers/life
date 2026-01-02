from django.shortcuts import render


def home(request):
    """
    Renders the homepage.
    """
    return render(request, 'home/index.html')


def about(request):
    """
    Renders the about page.
    """
    return render(request, 'home/about.html')


def inspirations(request):
    """
    Renders the inspirations page with random ordering.
    Ensures at least one card with flip_text appears in the second row (positions 5-10).
    """
    from inspirations_app.models import Inspiration
    import random

    all_inspirations = list(Inspiration.objects.all())
    random.shuffle(all_inspirations)

    # Ensure at least one card with flip_text is in the second row (indices 4-9)
    # Find cards with flip_text
    flip_text_cards = [card for card in all_inspirations if card.flip_text]

    if flip_text_cards:
        # Check if any flip_text card is already in positions 5-10 (indices 4-9)
        second_row_has_flip = any(
            all_inspirations[i].flip_text
            for i in range(4, min(10, len(all_inspirations)))
            if i < len(all_inspirations)
        )

        if not second_row_has_flip and len(all_inspirations) >= 10:
            # Find a flip_text card not in the second row
            flip_card_to_move = None
            for i, card in enumerate(all_inspirations):
                if card.flip_text and (i < 4 or i >= 10):
                    flip_card_to_move = card
                    original_index = i
                    break

            if flip_card_to_move:
                # Swap it with a random position in the second row
                target_index = random.randint(4, 9)
                all_inspirations[original_index], all_inspirations[target_index] = \
                    all_inspirations[target_index], all_inspirations[original_index]

        # Mark one flip_text card in the second row for auto-flip
        auto_flip_index = None
        for i in range(4, min(10, len(all_inspirations))):
            if i < len(all_inspirations) and all_inspirations[i].flip_text:
                auto_flip_index = i
                break
    else:
        auto_flip_index = None

    return render(request, 'home/inspirations.html', {
        'inspirations': all_inspirations,
        'auto_flip_index': auto_flip_index
    })


def life_metrics(request):
    """
    Renders the life metrics page with real habit data.
    """
    from settings.models import LifeTrackerColumn
    from datetime import date, datetime, timedelta
    from calendar import monthrange
    from django.db import connection
    from targets.views import get_column_data, parse_details_template
    import pytz
    import json

    # Get year from request, default to 2026
    year = int(request.GET.get('year', 2026))

    # Get user's timezone (default to America/Chicago)
    user_tz = pytz.timezone('America/Chicago')

    # Build month data - determine which habits were active on the last day of each month
    months_data = []
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Data structure to hold which days have data for each habit
    # Format: {month_num: {habit_column_name: [day1, day2, ...]}}
    habit_data = {}

    # Data structure to hold details text for each cell
    # Format: {month_num: {habit_column_name: {day: "details text"}}}
    habit_details = {}

    for month_num in range(1, 13):
        # Get the last day of the month
        last_day = monthrange(year, month_num)[1]
        last_date = date(year, month_num, last_day)

        # Get all habits that were active on the last day of this month
        active_habits = []
        habit_data[month_num] = {}
        habit_details[month_num] = {}

        for column in LifeTrackerColumn.objects.all():
            if column.is_active_on(last_date):
                active_habits.append({
                    'column_name': column.column_name,
                    'display_name': column.display_name,
                    'tooltip_text': column.tooltip_text,
                    'total_column_text': column.total_column_text or column.display_name.lower(),
                })

                # For each day in the month, check if data exists
                days_with_data = []
                habit_details[month_num][column.column_name] = {}

                for day in range(1, last_day + 1):
                    current_date = date(year, month_num, day)
                    day_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=user_tz)
                    day_end = datetime.combine(current_date, datetime.max.time()).replace(tzinfo=user_tz)

                    # Execute the SQL query to check if data exists
                    query = column.sql_query
                    params = []

                    # Replace parameters in the query
                    if ':day_start' in query:
                        query = query.replace(':day_start', '%s')
                        params.append(day_start)
                    if ':day_end' in query:
                        query = query.replace(':day_end', '%s')
                        params.append(day_end)
                    if ':current_date' in query:
                        query = query.replace(':current_date', '%s')
                        params.append(current_date)
                    if ':day' in query:
                        query = query.replace(':day', '%s')
                        params.append(current_date)

                    try:
                        with connection.cursor() as cursor:
                            cursor.execute(query, params)
                            result = cursor.fetchone()
                            # If count > 0, this day has data
                            if result and result[0] > 0:
                                days_with_data.append(day)

                                # Fetch details if details_display template exists
                                if column.details_display:
                                    records = get_column_data(
                                        column.column_name,
                                        day_start,
                                        day_end,
                                        current_date,
                                        user_tz,
                                        column.sql_query
                                    )
                                    if records:
                                        # Parse template for each record and join with ", "
                                        parsed_details = [
                                            parse_details_template(column.details_display, record)
                                            for record in records
                                        ]
                                        habit_details[month_num][column.column_name][day] = ', '.join(parsed_details)
                    except Exception as e:
                        print(f"Error executing query for {column.column_name} on {current_date}: {e}")

                habit_data[month_num][column.column_name] = days_with_data

        months_data.append({
            'month_num': month_num,
            'month_name': month_names[month_num - 1],
            'habits': active_habits,
            'days_in_month': last_day,
            'day_range': range(1, last_day + 1),
        })

    context = {
        'year': year,
        'months_data': months_data,
        'all_days': range(1, 32),  # Always show 31 columns
        'habit_data_json': json.dumps(habit_data),
        'habit_details_json': json.dumps(habit_details),
    }

    return render(request, 'home/life_metrics.html', context)


def writing(request):
    """
    Renders the writing page with images from database.
    """
    from writing.models import WritingPageImage, BookCover

    images = WritingPageImage.objects.filter(enabled=True).order_by('created_at')
    book_cover = BookCover.get_instance()

    return render(request, 'home/writing.html', {
        'images': images,
        'book_cover': book_cover
    })


def contact(request):
    """
    Renders the contact page.
    """
    return render(request, 'home/contact.html')
