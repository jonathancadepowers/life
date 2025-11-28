from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from inspirations_app.models import Inspiration
from PIL import Image
import io
import os


class Command(BaseCommand):
    help = 'Import inspiration images from a directory'

    def add_arguments(self, parser):
        parser.add_argument('directory', type=str, help='Directory containing images to import')

    def handle(self, *args, **options):
        directory = options['directory']

        if not os.path.exists(directory):
            self.stdout.write(self.style.ERROR(f'Directory does not exist: {directory}'))
            return

        # Get all image files
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
                # Parse filename: type_title.jpg
                name_without_ext = os.path.splitext(filename)[0]
                parts = name_without_ext.split('_', 1)

                if len(parts) != 2:
                    self.stdout.write(self.style.WARNING(
                        f'Skipping {filename}: Expected format type_title.jpg'
                    ))
                    skipped_count += 1
                    continue

                type_raw, title_raw = parts

                # Convert type to proper case
                type_raw_lower = type_raw.lower()
                if type_raw_lower in ['tvshow', 'tv_show', 'tv show']:
                    type_value = 'TV Show'
                elif type_raw_lower in ['podcastseries', 'podcast_series', 'podcast series']:
                    type_value = 'Podcast Series'
                else:
                    type_value = type_raw.capitalize()

                # Validate type
                valid_types = [choice[0] for choice in Inspiration.TYPE_CHOICES]
                if type_value not in valid_types:
                    self.stdout.write(self.style.WARNING(
                        f'Skipping {filename}: Invalid type "{type_value}". '
                        f'Valid types: {", ".join(valid_types)}'
                    ))
                    skipped_count += 1
                    continue

                # Convert title to proper case (capitalize each word)
                title = ' '.join(word.capitalize() for word in title_raw.replace('_', ' ').split())

                # Check if already exists
                if Inspiration.objects.filter(title=title, type=type_value).exists():
                    self.stdout.write(self.style.WARNING(
                        f'Skipping {filename}: "{title}" ({type_value}) already exists'
                    ))
                    skipped_count += 1
                    continue

                # Read and resize image
                image_path = os.path.join(directory, filename)
                img = Image.open(image_path)
                img = img.resize((256, 362), Image.Resampling.LANCZOS)

                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Save to BytesIO
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85)
                output.seek(0)

                # Create ContentFile with resized image
                resized_image = ContentFile(output.read(), name=filename)

                # Create Inspiration
                Inspiration.objects.create(
                    image=resized_image,
                    title=title,
                    type=type_value,
                    flip_text=''  # Empty flip text
                )

                self.stdout.write(self.style.SUCCESS(
                    f'Imported: {title} ({type_value})'
                ))
                imported_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Error processing {filename}: {str(e)}'
                ))
                error_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Import complete!'))
        self.stdout.write(f'  Imported: {imported_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        self.stdout.write(f'  Errors: {error_count}')
