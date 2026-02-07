"""
Django management command to sync nutrition data from Cronometer.

Usage:
    python manage.py sync_cronometer [--days=30]
"""
from django.core.management.base import BaseCommand
from datetime import datetime
from decimal import Decimal
import pytz

from nutrition.models import NutritionEntry
from nutrition.services.cronometer_client import CronometerClient


def _has_meaningful_data(day_data):
    """Return True if the day has any non-zero macros."""
    return (day_data['calories'] != 0 or day_data['fat'] != 0 or
            day_data['carbs'] != 0 or day_data['protein'] != 0)


class Command(BaseCommand):
    help = 'Sync nutrition data from Cronometer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days in the past to sync data from (default: 30)'
        )
        parser.add_argument(
            '--timezone',
            type=str,
            default='America/Los_Angeles',
            help='Timezone for interpreting Cronometer dates (default: America/Los_Angeles)'
        )

    def _process_day_data(self, day_data, user_tz):
        """Process a single day's nutrition data. Returns 'created', 'updated', or 'skipped'."""
        date_str = day_data['date']

        try:
            naive_dt = datetime.strptime(date_str, '%Y-%m-%d')
            consumption_dt = user_tz.localize(naive_dt)
        except ValueError as e:
            self.stdout.write(
                self.style.WARNING(f'Skipping invalid date {date_str}: {e}')
            )
            return 'skipped'

        if not _has_meaningful_data(day_data):
            return 'skipped'

        _, created = NutritionEntry.objects.update_or_create(
            source='Cronometer',
            source_id=date_str,
            defaults={
                'consumption_date': consumption_dt,
                'calories': Decimal(str(day_data['calories'])),
                'fat': Decimal(str(day_data['fat'])),
                'carbs': Decimal(str(day_data['carbs'])),
                'protein': Decimal(str(day_data['protein'])),
            }
        )

        return 'created' if created else 'updated'

    def handle(self, *_args, **options):
        days = options['days']

        self.stdout.write(f'Syncing Cronometer nutrition data for last {days} days...')

        try:
            client = CronometerClient()

            self.stdout.write('Fetching data from Cronometer...')
            nutrition_data = client.get_daily_nutrition_for_days(days)

            created_count = 0
            updated_count = 0
            skipped_count = 0

            user_tz = pytz.timezone(options['timezone'])

            for day_data in nutrition_data:
                result = self._process_day_data(day_data, user_tz)
                if result == 'created':
                    created_count += 1
                elif result == 'updated':
                    updated_count += 1
                else:
                    skipped_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n\u2713 Cronometer sync complete:\n'
                    f'  - {created_count} new entries created\n'
                    f'  - {updated_count} existing entries updated\n'
                    f'  - {skipped_count} entries skipped (no data)'
                )
            )

        except FileNotFoundError as e:
            self.stdout.write(
                self.style.ERROR(
                    f'\n\u2717 Cronometer CLI not found:\n{e}\n\n'
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
                    f'\n\u2717 Missing Cronometer credentials:\n{e}\n\n'
                    f'Please set environment variables:\n'
                    f'  CRONOMETER_USERNAME=your_email@example.com\n'
                    f'  CRONOMETER_PASSWORD=your_password'
                )
            )
            raise

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n\u2717 Error syncing Cronometer data: {e}')
            )
            raise
