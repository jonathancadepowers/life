"""
Django management command to sync workout data from Whoop API.

Usage:
    python manage.py sync_whoop [--days=30]
"""
from datetime import datetime, timedelta, timezone
from workouts.services.whoop_client import WhoopAPIClient
from workouts.models import Workout
from lifetracker.sync_utils import BaseSyncCommand


class Command(BaseSyncCommand):
    help = 'Sync workout data from Whoop API'
    source_name = 'Whoop'

    def sync(self, days, sync_all=False):
        self.stdout.write(self.style.SUCCESS('Starting Whoop workout sync...'))

        try:
            client = WhoopAPIClient()

            if sync_all:
                self.stdout.write('Syncing all available workouts...')
                start_date = datetime(2020, 1, 1)
            else:
                start_date = datetime.now(timezone.utc) - timedelta(days=days)
                self.stdout.write(f'Syncing workouts from last {days} days...')

            end_date = datetime.now(timezone.utc)

            self.stdout.write('Fetching workouts from Whoop API...')
            workouts_data = client.get_all_workouts(
                start_date=start_date,
                end_date=end_date
            )
            self.stdout.write(f'Retrieved {len(workouts_data)} workouts from Whoop')

            created_count = 0
            updated_count = 0
            skipped_count = 0

            for workout_data in workouts_data:
                result = self._process_workout(workout_data)
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
            self.stdout.write(f'  Total processed: {len(workouts_data)}')

            return self.make_result(
                created=created_count,
                updated=updated_count,
                skipped=skipped_count,
            )

        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'Configuration error: {e}'))
            self.stdout.write(self.style.WARNING(
                '\nMake sure you have set up your Whoop API credentials in .env file:'
            ))
            self.stdout.write('  WHOOP_CLIENT_ID')
            self.stdout.write('  WHOOP_CLIENT_SECRET')
            self.stdout.write('  WHOOP_ACCESS_TOKEN')
            self.stdout.write('  WHOOP_REFRESH_TOKEN')
            return self.make_error_result(str(e), auth_error=True)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error syncing workouts: {e}'))
            return self.make_error_result(str(e))

    def _process_workout(self, workout_data: dict) -> str:
        """
        Process a single workout from Whoop API and save to database.

        Returns:
            'created', 'updated', or 'skipped'
        """
        workout_id = workout_data.get('id')
        if not workout_id:
            self.stdout.write(self.style.WARNING('Skipping workout with no ID'))
            return 'skipped'

        score = workout_data.get('score')
        if not score:
            self.stdout.write(self.style.WARNING(
                f'Skipping workout {workout_id} - not yet scored'
            ))
            return 'skipped'

        try:
            start_time = datetime.fromisoformat(
                workout_data['start'].replace('Z', '+00:00')
            )
            end_time = datetime.fromisoformat(
                workout_data['end'].replace('Z', '+00:00')
            )
        except (KeyError, ValueError) as e:
            self.stdout.write(self.style.WARNING(
                f'Skipping workout {workout_id} - invalid timestamps: {e}'
            ))
            return 'skipped'

        # Convert kilojoules to calories (1 kJ = 0.239006 kcal)
        kilojoules = score.get('kilojoule')
        calories = round(kilojoules * 0.239006, 2) if kilojoules is not None else None

        # Convert distance from meters to miles (1 meter = 0.000621371 miles)
        distance_meters = score.get('distance_meter')
        distance_miles = round(distance_meters * 0.000621371, 2) if distance_meters is not None else None

        # Normalize sport_id: Whoop sometimes returns -1 for sauna sessions (should be 233)
        raw_sport_id = workout_data.get('sport_id', 0)
        normalized_sport_id = 233 if raw_sport_id == -1 else raw_sport_id

        workout_defaults = {
            'start': start_time,
            'end': end_time,
            'sport_id': normalized_sport_id,
            'average_heart_rate': score.get('average_heart_rate'),
            'max_heart_rate': score.get('max_heart_rate'),
            'calories_burned': calories,
            'distance_in_miles': distance_miles,
        }

        workout, created = Workout.objects.update_or_create(
            source='Whoop',
            source_id=workout_id,
            defaults=workout_defaults
        )

        if created:
            self.stdout.write(self.style.SUCCESS(
                f'✓ Created workout: {workout.start.strftime("%Y-%m-%d %H:%M")} '
                f'(Sport ID: {workout.sport_id})'
            ))
            return 'created'
        else:
            self.stdout.write(
                f'  Updated workout: {workout.start.strftime("%Y-%m-%d %H:%M")}'
            )
            return 'updated'
