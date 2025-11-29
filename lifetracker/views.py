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
    Renders the inspirations page with random ordering and random large images.
    """
    from inspirations_app.models import Inspiration
    import random

    inspirations_list = list(Inspiration.objects.all().order_by('?'))

    # Randomly mark some inspirations as "large" (2x2 grid cells)
    # Approximately 20-25% of images will be large
    for inspiration in inspirations_list:
        inspiration.is_large = random.random() < 0.25

    return render(request, 'home/inspirations.html', {'inspirations': inspirations_list})
