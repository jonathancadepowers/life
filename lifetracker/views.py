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
    Renders the life metrics page.
    """
    return render(request, 'home/life_metrics.html')


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
