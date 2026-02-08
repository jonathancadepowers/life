from django.core.management.base import BaseCommand
from inspirations_app.models import Inspiration
from inspirations_app.utils import get_youtube_trailer_url


class Command(BaseCommand):
    help = 'Populate YouTube URLs for existing films'

    def handle(self, *_args, **_options):
        films = Inspiration.objects.filter(type='Film', youtube_url__isnull=True)

        self.stdout.write(f'Found {films.count()} films without YouTube URLs')

        updated_count = 0
        failed_count = 0

        for film in films:
            self.stdout.write(f'Searching for: {film.title}...')
            youtube_url = get_youtube_trailer_url(film.title)

            if youtube_url:
                film.youtube_url = youtube_url
                film.save()
                self.stdout.write(self.style.SUCCESS(f'✅ {film.title}: {youtube_url}'))
                updated_count += 1
            else:
                self.stdout.write(self.style.WARNING(f'⚠️  {film.title}: No trailer found'))
                failed_count += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Complete!'))
        self.stdout.write(f'  Updated: {updated_count}')
        self.stdout.write(f'  Failed: {failed_count}')
