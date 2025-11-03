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
