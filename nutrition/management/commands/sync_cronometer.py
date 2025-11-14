"""
Django management command to sync nutrition data from Cronometer.

Usage:
    python manage.py sync_cronometer [--days=30]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import pytz

from nutrition.models import NutritionEntry
from nutrition.services.cronometer_client import CronometerClient


class Command(BaseCommand):
    help = 'Sync nutrition data from Cronometer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days in the past to sync data from (default: 30)'
        )

    def handle(self, *args, **options):
        days = options['days']

        self.stdout.write(f'Syncing Cronometer nutrition data for last {days} days...')

        try:
            # Initialize client
            client = CronometerClient()

            # Fetch data
            self.stdout.write('Fetching data from Cronometer...')
            nutrition_data = client.get_daily_nutrition_for_days(days)

            # Process each day's data
            created_count = 0
            updated_count = 0
            skipped_count = 0

            user_tz = pytz.timezone('America/Los_Angeles')  # TODO: Make this configurable

            for day_data in nutrition_data:
                # Parse the date string (YYYY-MM-DD format from Cronometer)
                date_str = day_data['date']
                try:
                    # Parse as naive datetime at midnight
                    naive_dt = datetime.strptime(date_str, '%Y-%m-%d')
                    # Localize to user's timezone
                    consumption_dt = user_tz.localize(naive_dt)
                except ValueError as e:
                    self.stdout.write(
                        self.style.WARNING(f'Skipping invalid date {date_str}: {e}')
                    )
                    skipped_count += 1
                    continue

                # Skip if no meaningful data
                if (day_data['calories'] == 0 and day_data['fat'] == 0 and
                    day_data['carbs'] == 0 and day_data['protein'] == 0):
                    skipped_count += 1
                    continue

                # Create or update the nutrition entry
                entry, created = NutritionEntry.objects.update_or_create(
                    source='Cronometer',
                    source_id=date_str,  # Use the date as the unique identifier
                    defaults={
                        'consumption_date': consumption_dt,
                        'calories': Decimal(str(day_data['calories'])),
                        'fat': Decimal(str(day_data['fat'])),
                        'carbs': Decimal(str(day_data['carbs'])),
                        'protein': Decimal(str(day_data['protein'])),
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            # Summary
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Cronometer sync complete:\n'
                    f'  - {created_count} new entries created\n'
                    f'  - {updated_count} existing entries updated\n'
                    f'  - {skipped_count} entries skipped (no data)'
                )
            )

        except FileNotFoundError as e:
            self.stdout.write(
                self.style.ERROR(
                    f'\n✗ Cronometer CLI not found:\n{e}\n\n'
                    f'Please build the Go CLI:\n'
                    f'  cd nutrition/cronometer_cli\n'
                    f'  go mod download\n'
                    f'  go build -o cronometer_export'
                )
            )
            raise

        except ValueError as e:
            self.stdout.write(
                self.style.ERROR(
                    f'\n✗ Missing Cronometer credentials:\n{e}\n\n'
                    f'Please set environment variables:\n'
                    f'  CRONOMETER_USERNAME=your_email@example.com\n'
                    f'  CRONOMETER_PASSWORD=your_password'
                )
            )
            raise

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n✗ Error syncing Cronometer data: {e}')
            )
            raise
