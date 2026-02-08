from datetime import datetime

import pytz
from django.utils import timezone


def get_user_timezone(request):
    """
    Get the user's timezone from the cookie set by JavaScript.
    Falls back to UTC if no timezone is set.
    """
    user_tz_name = request.COOKIES.get('user_timezone', 'UTC')
    try:
        return pytz.timezone(user_tz_name)
    except pytz.exceptions.UnknownTimeZoneError:
        return pytz.UTC


def get_user_today(request):
    """
    Get today's date in the user's timezone.
    Returns both the date object and timezone-aware start/end datetimes.
    """
    user_tz = get_user_timezone(request)
    now_in_user_tz = timezone.now().astimezone(user_tz)
    today = now_in_user_tz.date()

    # Create timezone-aware start and end of day in user's timezone
    today_start = user_tz.localize(datetime.combine(today, datetime.min.time()))
    today_end = user_tz.localize(datetime.combine(today, datetime.max.time()))

    return today, today_start, today_end
