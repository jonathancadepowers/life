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
    """
    from inspirations_app.models import Inspiration

    inspirations = Inspiration.objects.all().order_by('?')

    return render(request, 'home/inspirations.html', {'inspirations': inspirations})


def life_metrics(request):
    """
    Renders the life metrics page with real habit data.
    """
    from settings.models import LifeTrackerColumn
    from datetime import date
    from calendar import monthrange

    # Get year from request, default to 2025
    year = int(request.GET.get('year', 2025))

    # Build month data - determine which habits were active on the last day of each month
    months_data = []
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    for month_num in range(1, 13):
        # Get the last day of the month
        last_day = monthrange(year, month_num)[1]
        last_date = date(year, month_num, last_day)

        # Get all habits that were active on the last day of this month
        active_habits = []
        for column in LifeTrackerColumn.objects.all():
            if column.is_active_on(last_date):
                active_habits.append({
                    'column_name': column.column_name,
                    'display_name': column.display_name,
                })

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
