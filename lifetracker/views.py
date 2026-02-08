from django.shortcuts import render


def home(request):
    """
    Renders the homepage.
    """
    return render(request, "home/index.html")


def about(request):
    """
    Renders the about page.
    """
    return render(request, "home/about.html")


def _ensure_flip_card_in_second_row(cards):
    """
    Ensure at least one card with flip_text is in the second row (indices 4-9).
    Swaps a flip_text card into the second row if needed. Modifies cards in place.
    """
    import random

    second_row = range(4, min(10, len(cards)))
    if any(cards[i].flip_text for i in second_row):
        return

    if len(cards) < 10:
        return

    # Find a flip_text card outside the second row
    for i, card in enumerate(cards):
        if card.flip_text and (i < 4 or i >= 10):
            target = random.randint(4, 9)
            cards[i], cards[target] = cards[target], cards[i]
            return


def _find_auto_flip_index(cards):
    """
    Find the index of the first card with flip_text in the second row (indices 4-9).
    Returns the index, or None if no such card exists.
    """
    for i in range(4, min(10, len(cards))):
        if cards[i].flip_text:
            return i
    return None


def inspirations(request):
    """
    Renders the inspirations page with random ordering.
    Ensures at least one card with flip_text appears in the second row (positions 5-10).
    """
    from inspirations_app.models import Inspiration
    import random

    all_inspirations = list(Inspiration.objects.all())
    random.shuffle(all_inspirations)

    has_flip_cards = any(card.flip_text for card in all_inspirations)
    auto_flip_index = None

    if has_flip_cards:
        _ensure_flip_card_in_second_row(all_inspirations)
        auto_flip_index = _find_auto_flip_index(all_inspirations)

    return render(
        request, "home/inspirations.html", {"inspirations": all_inspirations, "auto_flip_index": auto_flip_index}
    )


def _build_query_params(query, day_start, day_end, current_date):
    """
    Replace date placeholders in a SQL query with %s and build the params list.
    Returns (processed_query, params).
    """
    params = []
    if ":day_start" in query:
        query = query.replace(":day_start", "%s")
        params.append(day_start)
    if ":day_end" in query:
        query = query.replace(":day_end", "%s")
        params.append(day_end)
    if ":current_date" in query:
        query = query.replace(":current_date", "%s")
        params.append(current_date)
    if ":day" in query:
        query = query.replace(":day", "%s")
        params.append(current_date)
    return query, params


def _collect_column_daily_data(column, year, month_num, last_day, user_tz):
    """
    For a single column and month, collect which days have data and their details.
    Returns (days_with_data, details_by_day).
    """
    from datetime import date, datetime
    from django.db import connection
    from targets.views import get_column_data, parse_details_template

    days_with_data = []
    details_by_day = {}

    for day in range(1, last_day + 1):
        current_date = date(year, month_num, day)
        day_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=user_tz)
        day_end = datetime.combine(current_date, datetime.max.time()).replace(tzinfo=user_tz)

        query, params = _build_query_params(column.sql_query, day_start, day_end, current_date)

        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                if not (result and result[0] > 0):
                    continue

                days_with_data.append(day)

                if not column.details_display:
                    continue

                records = get_column_data(
                    column.column_name,
                    day_start,
                    day_end,
                    current_date,
                    user_tz,
                    column.sql_query,
                )
                if records:
                    parsed = [parse_details_template(column.details_display, r) for r in records]
                    details_by_day[day] = ", ".join(parsed)
        except Exception as e:
            print(f"Error executing query for {column.column_name} on {current_date}: {e}")

    return days_with_data, details_by_day


def life_metrics(request):
    """
    Renders the life metrics page with real habit data.
    """
    from settings.models import LifeTrackerColumn
    from datetime import date
    from calendar import monthrange
    import pytz
    import json

    year = int(request.GET.get("year", 2026))
    user_tz = pytz.timezone("America/Chicago")

    months_data = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    habit_data = {}
    habit_details = {}
    all_columns = list(LifeTrackerColumn.objects.all())

    for month_num in range(1, 13):
        last_day = monthrange(year, month_num)[1]
        last_date = date(year, month_num, last_day)

        active_habits = []
        habit_data[month_num] = {}
        habit_details[month_num] = {}

        for column in all_columns:
            if not column.is_active_on(last_date):
                continue

            active_habits.append(
                {
                    "column_name": column.column_name,
                    "display_name": column.display_name,
                    "tooltip_text": column.tooltip_text,
                    "total_column_text": column.total_column_text or column.display_name.lower(),
                }
            )

            days_with_data, details_by_day = _collect_column_daily_data(
                column,
                year,
                month_num,
                last_day,
                user_tz,
            )
            habit_data[month_num][column.column_name] = days_with_data
            habit_details[month_num][column.column_name] = details_by_day

        months_data.append(
            {
                "month_num": month_num,
                "month_name": month_names[month_num - 1],
                "habits": active_habits,
                "days_in_month": last_day,
                "day_range": range(1, last_day + 1),
            }
        )

    context = {
        "year": year,
        "months_data": months_data,
        "all_days": range(1, 32),
        "habit_data_json": json.dumps(habit_data),
        "habit_details_json": json.dumps(habit_details),
    }

    return render(request, "home/life_metrics.html", context)


def writing(request):
    """
    Renders the writing page with images from database.
    """
    from writing.models import WritingPageImage, BookCover

    images = WritingPageImage.objects.filter(enabled=True).order_by("created_at")
    book_cover = BookCover.get_instance()

    return render(request, "home/writing.html", {"images": images, "book_cover": book_cover})


def contact(request):
    """
    Renders the contact page.
    """
    return render(request, "home/contact.html")
