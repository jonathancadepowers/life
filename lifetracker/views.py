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
    Renders the inspirations page.
    """
    from inspirations_app.models import Inspiration

    inspirations = Inspiration.objects.all()

    return render(request, 'home/inspirations.html', {'inspirations': inspirations})
