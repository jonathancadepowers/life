from django.core.management.base import BaseCommand
from inspirations_app.models import Inspiration
from PIL import Image


class Command(BaseCommand):
    help = 'Add * to titles of Film inspirations with gray placeholder images'

    def handle(self, *args, **options):
        # Get all Film inspirations
        film_inspirations = Inspiration.objects.filter(type='Film')

        updated_count = 0
        skipped_count = 0

        for inspiration in film_inspirations:
            # Skip if title already has *
            if inspiration.title.startswith('*'):
                self.stdout.write(f'Skipping "{inspiration.title}" - already has *')
                skipped_count += 1
                continue

            try:
                # Open the image and check if it's a gray placeholder
                # Placeholder images are solid gray #cccccc (RGB: 204, 204, 204)
                img = Image.open(inspiration.image)

                # Sample a few pixels to check if it's the gray placeholder
                # Get pixel at center of image
                width, height = img.size
                center_pixel = img.getpixel((width // 2, height // 2))

                # Check if it's gray (all RGB values equal and around 204)
                if isinstance(center_pixel, tuple) and len(center_pixel) >= 3:
                    r, g, b = center_pixel[:3]
                    # Check if it's the placeholder gray color (allow some tolerance for JPEG compression)
                    if abs(r - 204) <= 10 and abs(g - 204) <= 10 and abs(b - 204) <= 10 and abs(r - g) <= 5 and abs(g - b) <= 5:
                        # It's a placeholder - add * to title
                        inspiration.title = '*' + inspiration.title
                        inspiration.save()
                        self.stdout.write(self.style.SUCCESS(f'Updated "{inspiration.title}"'))
                        updated_count += 1
                    else:
                        self.stdout.write(f'Skipping "{inspiration.title}" - has custom image')
                        skipped_count += 1
                else:
                    self.stdout.write(f'Skipping "{inspiration.title}" - unexpected pixel format')
                    skipped_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing "{inspiration.title}": {str(e)}'))
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(f'\nDone! Updated {updated_count} films, skipped {skipped_count}.'))
