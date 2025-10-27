"""
Django management command to sync workout data from Whoop API.

Usage:
    python manage.py sync_whoop [--days=30]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from workouts.services.whoop_client import WhoopAPIClient
from workouts.models import Workout


class Command(BaseCommand):
    help = 'Sync workout data from Whoop API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days in the past to sync workouts from (default: 30)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync all workouts (ignores --days parameter)'
        )

    def handle(self, *args, **options):
        days = options['days']
        sync_all = options['all']

        self.stdout.write(self.style.SUCCESS('Starting Whoop workout sync...'))

        try:
            # Initialize Whoop client
            client = WhoopAPIClient()

            # Determine date range
            if sync_all:
                self.stdout.write('Syncing all available workouts...')
                start_date = datetime(2020, 1, 1)  # Whoop launched around 2015, use safe date
            else:
                start_date = datetime.utcnow() - timedelta(days=days)
                self.stdout.write(f'Syncing workouts from last {days} days...')

            end_date = datetime.utcnow()

            # Fetch workouts from Whoop
            self.stdout.write('Fetching workouts from Whoop API...')
            workouts_data = client.get_all_workouts(
                start_date=start_date,
                end_date=end_date
            )

            self.stdout.write(f'Retrieved {len(workouts_data)} workouts from Whoop')

            # Process and save workouts
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

            # Summary
            self.stdout.write(self.style.SUCCESS(
                f'\nSync completed successfully!'
            ))
            self.stdout.write(f'  Created: {created_count}')
            self.stdout.write(f'  Updated: {updated_count}')
            self.stdout.write(f'  Skipped: {skipped_count}')
            self.stdout.write(f'  Total processed: {len(workouts_data)}')

        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'Configuration error: {e}'))
            self.stdout.write(self.style.WARNING(
                '\nMake sure you have set up your Whoop API credentials in .env file:'
            ))
            self.stdout.write('  WHOOP_CLIENT_ID')
            self.stdout.write('  WHOOP_CLIENT_SECRET')
            self.stdout.write('  WHOOP_ACCESS_TOKEN')
            self.stdout.write('  WHOOP_REFRESH_TOKEN')
            raise  # Re-raise so sync_all can report the failure
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error syncing workouts: {e}'))
            raise

    def _process_workout(self, workout_data: dict) -> str:
        """
        Process a single workout from Whoop API and save to database.

        Args:
            workout_data: Workout data from Whoop API

        Returns:
            'created', 'updated', or 'skipped'
        """
        # Extract workout ID
        workout_id = workout_data.get('id')
        if not workout_id:
            self.stdout.write(self.style.WARNING(f'Skipping workout with no ID'))
            return 'skipped'

        # Check if workout has score (some workouts may not be scored yet)
        score = workout_data.get('score')
        if not score:
            self.stdout.write(self.style.WARNING(
                f'Skipping workout {workout_id} - not yet scored'
            ))
            return 'skipped'

        # Parse workout data
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
        kilojoules = score.get('kilojoule', 0)
        calories = kilojoules * 0.239006 if kilojoules else None

        # Prepare workout data for our model
        workout_defaults = {
            'start': start_time,
            'end': end_time,
            'sport_id': workout_data.get('sport_id', 0),
            'average_heart_rate': score.get('average_heart_rate'),
            'max_heart_rate': score.get('max_heart_rate'),
            'calories_burned': round(calories, 2) if calories else None,
        }

        # Create or update workout
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
