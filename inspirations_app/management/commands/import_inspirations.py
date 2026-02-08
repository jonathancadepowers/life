from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from inspirations_app.models import Inspiration
from PIL import Image
import io
import os


_TV_SHOW = 'TV Show'
_PODCAST_SERIES = 'Podcast Series'

_TYPE_ALIASES = {
    'tvshow': _TV_SHOW,
    'tv_show': _TV_SHOW,
    'tv show': _TV_SHOW,
    'podcastseries': _PODCAST_SERIES,
    'podcast_series': _PODCAST_SERIES,
    'podcast series': _PODCAST_SERIES,
}


def _resolve_type(type_raw):
    """Resolve a raw type string to a valid Inspiration type value, or None."""
    type_value = _TYPE_ALIASES.get(type_raw.lower(), type_raw.capitalize())
    valid_types = [choice[0] for choice in Inspiration.TYPE_CHOICES]
    return type_value if type_value in valid_types else None


def _convert_to_rgb(img):
    """Convert an image to RGB mode, handling RGBA/P/LA with white background."""
    if img.mode in ('RGBA', 'P', 'LA'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        mask = img.split()[-1] if img.mode in ('RGBA', 'LA') else None
        background.paste(img, mask=mask)
        return background
    if img.mode != 'RGB':
        return img.convert('RGB')
    return img


def _resize_and_encode(image_path, filename):
    """Open, resize to 256x362, convert to RGB, and return a ContentFile."""
    img = Image.open(image_path)
    img = img.resize((256, 362), Image.Resampling.LANCZOS)
    img = _convert_to_rgb(img)

    output = io.BytesIO()
    img.save(output, format='JPEG', quality=85)
    output.seek(0)
    return ContentFile(output.read(), name=filename)


class Command(BaseCommand):
    help = 'Import inspiration images from a directory'

    def add_arguments(self, parser):
        parser.add_argument('directory', type=str, help='Directory containing images to import')

    def _process_file(self, directory, filename):
        """Process a single image file. Returns 'imported', 'skipped', or 'error'."""
        name_without_ext = os.path.splitext(filename)[0]
        parts = name_without_ext.split('_', 1)

        if len(parts) != 2:
            self.stdout.write(self.style.WARNING(
                f'Skipping {filename}: Expected format type_title.jpg'
            ))
            return 'skipped'

        type_raw, title_raw = parts
        type_value = _resolve_type(type_raw)

        if type_value is None:
            valid_types = [choice[0] for choice in Inspiration.TYPE_CHOICES]
            self.stdout.write(self.style.WARNING(
                f'Skipping {filename}: Invalid type "{type_raw.capitalize()}". '
                f'Valid types: {", ".join(valid_types)}'
            ))
            return 'skipped'

        title = ' '.join(word.capitalize() for word in title_raw.replace('_', ' ').split())

        if Inspiration.objects.filter(title=title, type=type_value).exists():
            self.stdout.write(self.style.WARNING(
                f'Skipping {filename}: "{title}" ({type_value}) already exists'
            ))
            return 'skipped'

        image_path = os.path.join(directory, filename)
        resized_image = _resize_and_encode(image_path, filename)

        Inspiration.objects.create(
            image=resized_image,
            title=title,
            type=type_value,
            flip_text=''
        )

        self.stdout.write(self.style.SUCCESS(f'Imported: {title} ({type_value})'))
        return 'imported'

    def handle(self, *_args, **options):
        directory = options['directory']

        if not os.path.exists(directory):
            self.stdout.write(self.style.ERROR(f'Directory does not exist: {directory}'))
            return

        image_files = [f for f in os.listdir(directory)
                      if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]

        if not image_files:
            self.stdout.write(self.style.WARNING(f'No image files found in {directory}'))
            return

        self.stdout.write(f'Found {len(image_files)} images to import')

        imported_count = 0
        skipped_count = 0
        error_count = 0

        for filename in image_files:
            try:
                result = self._process_file(directory, filename)
                if result == 'imported':
                    imported_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Error processing {filename}: {str(e)}'
                ))
                error_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Import complete!'))
        self.stdout.write(f'  Imported: {imported_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        self.stdout.write(f'  Errors: {error_count}')
