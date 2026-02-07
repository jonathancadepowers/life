from django.core.management.base import BaseCommand
from inspirations_app.models import Inspiration
from PIL import Image


def _is_placeholder_gray(pixel):
    """Check if a pixel is the gray placeholder color (approx #cccccc)."""
    if not isinstance(pixel, tuple) or len(pixel) < 3:
        return False
    r, g, b = pixel[:3]
    tolerance = 10
    channel_diff = 5
    return (abs(r - 204) <= tolerance and abs(g - 204) <= tolerance and
            abs(b - 204) <= tolerance and abs(r - g) <= channel_diff and
            abs(g - b) <= channel_diff)


class Command(BaseCommand):
    help = 'Add * to titles of Film inspirations with gray placeholder images'

    def _process_inspiration(self, inspiration):
        """Check one inspiration and mark it if placeholder. Returns 'updated', 'skipped', or 'error'."""
        if inspiration.title.startswith('*'):
            self.stdout.write(f'Skipping "{inspiration.title}" - already has *')
            return 'skipped'

        try:
            img = Image.open(inspiration.image)
            width, height = img.size
            center_pixel = img.getpixel((width // 2, height // 2))

            if _is_placeholder_gray(center_pixel):
                inspiration.title = '*' + inspiration.title
                inspiration.save()
                self.stdout.write(self.style.SUCCESS(f'Updated "{inspiration.title}"'))
                return 'updated'

            self.stdout.write(f'Skipping "{inspiration.title}" - has custom image')
            return 'skipped'

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error processing "{inspiration.title}": {str(e)}'))
            return 'error'

    def handle(self, *_args, **_options):
        film_inspirations = Inspiration.objects.filter(type='Film')

        updated_count = 0
        skipped_count = 0

        for inspiration in film_inspirations:
            result = self._process_inspiration(inspiration)
            if result == 'updated':
                updated_count += 1
            else:
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(f'\nDone! Updated {updated_count} films, skipped {skipped_count}.'))
