"""
Django management command to sync weight data from Withings API.

Usage:
    python manage.py sync_withings [--days=30]
"""
from datetime import datetime, timedelta, timezone
from weight.services.withings_client import WithingsAPIClient
from weight.models import WeighIn
from lifetracker.sync_utils import BaseSyncCommand


class Command(BaseSyncCommand):
    help = 'Sync weight measurements from Withings API'
    source_name = 'Withings'

    def sync(self, days, sync_all=False):
        self.stdout.write(self.style.SUCCESS('Starting Withings weight sync...'))

        try:
            client = WithingsAPIClient()

            if sync_all:
                self.stdout.write('Syncing all available measurements...')
                start_date = datetime(2010, 1, 1)
            else:
                start_date = datetime.now(timezone.utc) - timedelta(days=days)
                self.stdout.write(f'Syncing measurements from last {days} days...')

            end_date = datetime.now(timezone.utc)

            self.stdout.write('Fetching measurements from Withings API...')
            measurements_data = client.get_all_weight_measurements(
                start_date=start_date,
                end_date=end_date
            )
            self.stdout.write(f'Retrieved {len(measurements_data)} measurement groups from Withings')

            created_count = 0
            updated_count = 0
            skipped_count = 0

            for measurement_group in measurements_data:
                result = self._process_measurement(measurement_group)
                if result == 'created':
                    created_count += 1
                elif result == 'updated':
                    updated_count += 1
                else:
                    skipped_count += 1

            self.stdout.write(self.style.SUCCESS('\nSync completed successfully!'))
            self.stdout.write(f'  Created: {created_count}')
            self.stdout.write(f'  Updated: {updated_count}')
            self.stdout.write(f'  Skipped: {skipped_count}')
            self.stdout.write(f'  Total processed: {len(measurements_data)}')

            return self.make_result(
                created=created_count,
                updated=updated_count,
                skipped=skipped_count,
            )

        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'Configuration error: {e}'))
            self.stdout.write(self.style.WARNING(
                '\nMake sure you have set up your Withings API credentials in .env file:'
            ))
            self.stdout.write('  WITHINGS_CLIENT_ID')
            self.stdout.write('  WITHINGS_CLIENT_SECRET')
            self.stdout.write('  WITHINGS_ACCESS_TOKEN')
            self.stdout.write('  WITHINGS_REFRESH_TOKEN')
            return self.make_error_result(str(e), auth_error=True)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error syncing measurements: {e}'))
            return self.make_error_result(str(e))

    def _process_measurement(self, measurement_group: dict) -> str:
        """
        Process a single measurement group from Withings API and save to database.

        Returns:
            'created', 'updated', or 'skipped'
        """
        group_id = measurement_group.get('grpid')
        if not group_id:
            self.stdout.write(self.style.WARNING('Skipping measurement with no group ID'))
            return 'skipped'

        measurement_timestamp = measurement_group.get('date')
        if not measurement_timestamp:
            self.stdout.write(self.style.WARNING(
                f'Skipping measurement {group_id} - no timestamp'
            ))
            return 'skipped'

        measurement_time = datetime.fromtimestamp(measurement_timestamp, tz=timezone.utc)

        measures = measurement_group.get('measures', [])
        weight_measure = None

        for measure in measures:
            if measure.get('type') == 1:  # Type 1 = weight
                weight_measure = measure
                break

        if not weight_measure:
            self.stdout.write(self.style.WARNING(
                f'Skipping measurement {group_id} - no weight data'
            ))
            return 'skipped'

        value = weight_measure.get('value')
        unit = weight_measure.get('unit')

        if value is None or unit is None:
            self.stdout.write(self.style.WARNING(
                f'Skipping measurement {group_id} - invalid weight value'
            ))
            return 'skipped'

        # Calculate weight: Withings returns value * 10^unit (in kg)
        weight_kg = value * (10 ** unit)
        weight_lbs = weight_kg * 2.20462  # Convert to pounds

        weighin_defaults = {
            'measurement_time': measurement_time,
            'weight': round(weight_lbs, 2),
        }

        weighin, created = WeighIn.objects.update_or_create(
            source='Withings',
            source_id=str(group_id),
            defaults=weighin_defaults
        )

        if created:
            self.stdout.write(self.style.SUCCESS(
                f'✓ Created measurement: {weighin.measurement_time.strftime("%Y-%m-%d %H:%M")} '
                f'- {weighin.weight} lbs'
            ))
            return 'created'
        else:
            self.stdout.write(
                f'  Updated measurement: {weighin.measurement_time.strftime("%Y-%m-%d %H:%M")}'
            )
            return 'updated'
