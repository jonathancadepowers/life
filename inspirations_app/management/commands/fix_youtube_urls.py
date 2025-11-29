from django.core.management.base import BaseCommand
from inspirations_app.models import Inspiration
from inspirations_app.utils import get_youtube_trailer_url, validate_youtube_url


class Command(BaseCommand):
    help = 'Fix broken YouTube URLs for films'

    def handle(self, *args, **options):
        films = Inspiration.objects.filter(type='Film')

        self.stdout.write(f'Checking {films.count()} films...\n')

        fixed_count = 0
        already_valid_count = 0
        failed_count = 0

        for film in films:
            # Check if current URL is valid
            if film.youtube_url and validate_youtube_url(film.youtube_url):
                self.stdout.write(self.style.SUCCESS(f'✅ {film.title}: URL is valid'))
                already_valid_count += 1
                continue

            # Current URL is invalid or missing, try to find a new one
            self.stdout.write(f'🔍 Searching for new URL: {film.title}...')
            new_url = get_youtube_trailer_url(film.title)

            if new_url:
                film.youtube_url = new_url
                film.save()
                self.stdout.write(self.style.SUCCESS(f'✅ Fixed: {film.title} -> {new_url}'))
                fixed_count += 1
            else:
                self.stdout.write(self.style.WARNING(f'⚠️  {film.title}: No valid trailer found'))
                failed_count += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Complete!'))
        self.stdout.write(f'  Already valid: {already_valid_count}')
        self.stdout.write(f'  Fixed: {fixed_count}')
        self.stdout.write(f'  Failed: {failed_count}')
