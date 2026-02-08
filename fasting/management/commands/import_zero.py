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
    help = "Import fasting data from Zero app JSON export (biodata.json)"

    def add_arguments(self, parser):
        parser.add_argument("json_file", type=str, help="Path to the biodata.json file from Zero app export")
        parser.add_argument(
            "--dry-run", action="store_true", help="Preview what would be imported without actually importing"
        )

    def _load_fast_data(self, json_file):
        """Load and validate fast_data from a JSON file.

        Returns the fast_data list, or None if loading/validation fails.
        """
        if not os.path.exists(json_file):
            self.stdout.write(self.style.ERROR(f"File not found: {json_file}"))
            return None

        self.stdout.write(f"Reading file: {json_file}")
        with open(json_file, "r") as f:
            data = json.load(f)

        if "fast_data" not in data:
            self.stdout.write(
                self.style.ERROR(
                    'No "fast_data" key found in JSON file. '
                    "Make sure you are using the biodata.json file from Zero export."
                )
            )
            return None

        return data["fast_data"]

    def _count_results(self, fast_data, dry_run):
        """Process all fast records and return (created, updated, skipped) counts."""
        counts = {"created": 0, "updated": 0, "skipped": 0}
        for fast_record in fast_data:
            result = self._process_fast(fast_record, dry_run)
            counts[result] = counts.get(result, 0) + 1
        return counts["created"], counts["updated"], counts["skipped"]

    def _print_summary(self, dry_run, created_count, updated_count, skipped_count, total):
        """Print the import summary."""
        prefix = "DRY RUN " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"\n{prefix}Import completed!"))
        label = "Would create" if dry_run else "Created"
        self.stdout.write(f"  {label}: {created_count}")
        label = "Would update" if dry_run else "Updated"
        self.stdout.write(f"  {label}: {updated_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        self.stdout.write(f"  Total processed: {total}")

    def handle(self, *_args, **options):
        json_file = options["json_file"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No data will be imported"))

        self.stdout.write(self.style.SUCCESS("Starting Zero fasting data import..."))

        try:
            fast_data = self._load_fast_data(json_file)
            if fast_data is None:
                return

            self.stdout.write(f"Found {len(fast_data)} fasting sessions in file")
            created, updated, skipped = self._count_results(fast_data, dry_run)
            self._print_summary(dry_run, created, updated, skipped, len(fast_data))

        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f"Invalid JSON file: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing fasting data: {e}"))
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
        fast_id = fast_record.get("FastID")
        if not fast_id:
            self.stdout.write(self.style.WARNING("Skipping fast with no FastID"))
            return "skipped"

        # Parse timestamps
        try:
            start_time = datetime.fromisoformat(fast_record["StartDTM"].replace("Z", "+00:00"))

            # EndDTM might be null for incomplete fasts
            end_dtm = fast_record.get("EndDTM")
            end_time = None
            if end_dtm:
                end_time = datetime.fromisoformat(end_dtm.replace("Z", "+00:00"))
        except (KeyError, ValueError) as e:
            self.stdout.write(self.style.WARNING(f"Skipping fast {fast_id} - invalid timestamps: {e}"))
            return "skipped"

        # Skip fasts without an end time (incomplete)
        if not end_time:
            self.stdout.write(self.style.WARNING(f"Skipping fast {fast_id} - no end time (incomplete fast)"))
            return "skipped"

        # Calculate duration and skip if less than 12 hours
        duration_timedelta = end_time - start_time
        duration_hours = duration_timedelta.total_seconds() / 3600

        if duration_hours < 12:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipping fast {fast_id} - duration {duration_hours:.1f}h is less than 12 hours minimum"
                )
            )
            return "skipped"

        # Prepare fasting session data
        fast_defaults = {
            "duration": round(duration_hours, 2),
            "fast_end_date": end_time,
        }

        # Check if already exists (for dry-run preview)
        if dry_run:
            exists = FastingSession.objects.filter(source="Zero", source_id=fast_id).exists()

            action = "update" if exists else "create"
            self.stdout.write(
                f'Would {action}: {duration_hours:.1f}h fast ending {end_time.strftime("%Y-%m-%d %H:%M")}'
            )
            return f"{action}d"

        # Create or update fasting session
        fast, created = FastingSession.objects.update_or_create(
            source="Zero", source_id=fast_id, defaults=fast_defaults
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Created: {fast.duration}h fast ending {fast.fast_end_date.strftime("%Y-%m-%d %H:%M")}'
                )
            )
            return "created"
        else:
            self.stdout.write(
                f'  Updated: {fast.duration}h fast ending {fast.fast_end_date.strftime("%Y-%m-%d %H:%M")}'
            )
            return "updated"
