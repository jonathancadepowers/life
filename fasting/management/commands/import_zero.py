"""
Django management command to import fasting data from Zero app export.

Usage:
    python manage.py import_zero <path_to_biodata.json>
    python manage.py import_zero import/temp/zero_data/zero-fasting-data_*/biodata.json
"""
from django.core.management.base import BaseCommand
from datetime import datetime
from fasting.models import FastingSession
import json
import os


class Command(BaseCommand):
    help = 'Import fasting data from Zero app JSON export (biodata.json)'

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to the biodata.json file from Zero app export'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be imported without actually importing'
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))

        self.stdout.write(self.style.SUCCESS('Starting Zero fasting data import...'))

        # Check if file exists
        if not os.path.exists(json_file):
            self.stdout.write(self.style.ERROR(f'File not found: {json_file}'))
            return

        try:
            # Load JSON data
            self.stdout.write(f'Reading file: {json_file}')
            with open(json_file, 'r') as f:
                data = json.load(f)

            # Extract fast_data
            if 'fast_data' not in data:
                self.stdout.write(self.style.ERROR(
                    'No "fast_data" key found in JSON file. '
                    'Make sure you are using the biodata.json file from Zero export.'
                ))
                return

            fast_data = data['fast_data']
            self.stdout.write(f'Found {len(fast_data)} fasting sessions in file')

            # Process fasting sessions
            created_count = 0
            updated_count = 0
            skipped_count = 0

            for fast_record in fast_data:
                result = self._process_fast(fast_record, dry_run)
                if result == 'created':
                    created_count += 1
                elif result == 'updated':
                    updated_count += 1
                else:
                    skipped_count += 1

            # Summary
            self.stdout.write(self.style.SUCCESS(
                f'\n{"DRY RUN " if dry_run else ""}Import completed!'
            ))
            self.stdout.write(f'  Would create: {created_count}' if dry_run else f'  Created: {created_count}')
            self.stdout.write(f'  Would update: {updated_count}' if dry_run else f'  Updated: {updated_count}')
            self.stdout.write(f'  Skipped: {skipped_count}')
            self.stdout.write(f'  Total processed: {len(fast_data)}')

        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f'Invalid JSON file: {e}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error importing fasting data: {e}'))
            raise

    def _process_fast(self, fast_record: dict, dry_run: bool = False) -> str:
        """
        Process a single fasting record from Zero app and save to database.

        Args:
            fast_record: Fasting record from Zero app JSON
            dry_run: If True, don't actually save to database

        Returns:
            'created', 'updated', or 'skipped'
        """
        # Extract fast ID
        fast_id = fast_record.get('FastID')
        if not fast_id:
            self.stdout.write(self.style.WARNING('Skipping fast with no FastID'))
            return 'skipped'

        # Parse timestamps
        try:
            start_time = datetime.fromisoformat(
                fast_record['StartDTM'].replace('Z', '+00:00')
            )

            # EndDTM might be null for incomplete fasts
            end_dtm = fast_record.get('EndDTM')
            end_time = None
            if end_dtm:
                end_time = datetime.fromisoformat(
                    end_dtm.replace('Z', '+00:00')
                )
        except (KeyError, ValueError) as e:
            self.stdout.write(self.style.WARNING(
                f'Skipping fast {fast_id} - invalid timestamps: {e}'
            ))
            return 'skipped'

        # Skip fasts without an end time (incomplete)
        if not end_time:
            self.stdout.write(self.style.WARNING(
                f'Skipping fast {fast_id} - no end time (incomplete fast)'
            ))
            return 'skipped'

        # Calculate duration and skip if less than 12 hours
        duration = end_time - start_time
        duration_hours = duration.total_seconds() / 3600

        if duration_hours < 12:
            self.stdout.write(self.style.WARNING(
                f'Skipping fast {fast_id} - duration {duration_hours:.1f}h is less than 12 hours minimum'
            ))
            return 'skipped'

        # Prepare fasting session data
        fast_defaults = {
            'start': start_time,
            'end': end_time,
        }

        # Check if already exists (for dry-run preview)
        if dry_run:
            exists = FastingSession.objects.filter(
                source='Zero',
                source_id=fast_id
            ).exists()

            action = 'update' if exists else 'create'
            duration_hours = (end_time - start_time).total_seconds() / 3600
            self.stdout.write(
                f'Would {action}: {start_time.strftime("%Y-%m-%d %H:%M")} - '
                f'{end_time.strftime("%Y-%m-%d %H:%M")} ({duration_hours:.1f}h)'
            )
            return f'{action}d'

        # Create or update fasting session
        fast, created = FastingSession.objects.update_or_create(
            source='Zero',
            source_id=fast_id,
            defaults=fast_defaults
        )

        if created:
            duration_hours = fast.duration_hours or 0
            self.stdout.write(self.style.SUCCESS(
                f'✓ Created: {fast.start.strftime("%Y-%m-%d %H:%M")} - '
                f'{fast.end.strftime("%Y-%m-%d %H:%M")} ({duration_hours:.1f}h)'
            ))
            return 'created'
        else:
            self.stdout.write(
                f'  Updated: {fast.start.strftime("%Y-%m-%d %H:%M")}'
            )
            return 'updated'
