"""
Django management command to sync all data sources.

This master sync command orchestrates syncing data from all configured sources:
- Whoop workouts
- Withings weight measurements
- Toggl time entries
- Future: Food tracking
- Future: Fasting tracking

Usage:
    python manage.py sync_all [--days=30]

This command is ideal for scheduled jobs (cron, etc.)
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from datetime import datetime


class Command(BaseCommand):
    help = 'Sync data from all configured sources (Whoop, food, weight, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days in the past to sync data from (default: 30)'
        )
        parser.add_argument(
            '--whoop-only',
            action='store_true',
            help='Only sync Whoop data (skip other sources)'
        )

    def handle(self, *args, **options):
        days = options['days']
        whoop_only = options['whoop_only']

        start_time = datetime.now()

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  LIFE TRACKER - MASTER SYNC'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Started at: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write(f'Syncing last {days} days of data...\n')

        results = {}

        # Sync Whoop workouts
        results['whoop'] = self._sync_whoop(days)

        # Sync Withings weight measurements
        if not whoop_only:
            results['withings'] = self._sync_withings(days)
            results['toggl'] = self._sync_toggl(days)
            # results['food'] = self._sync_food(days)
            # results['fasting'] = self._sync_fasting(days)

        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('  SYNC SUMMARY'))
        self.stdout.write('=' * 60)

        for source, result in results.items():
            if result['success']:
                self.stdout.write(self.style.SUCCESS(
                    f'✓ {source.upper()}: {result["message"]}'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f'✗ {source.upper()}: {result["message"]}'
                ))

        self.stdout.write(f'\nCompleted in {duration:.1f} seconds')
        self.stdout.write('=' * 60)

    def _sync_whoop(self, days):
        """Sync Whoop workout data."""
        self.stdout.write(self.style.HTTP_INFO('\n[1/3] Syncing Whoop workouts...'))

        try:
            # Call the sync_whoop command
            call_command('sync_whoop', days=days, verbosity=0)

            # Note: We're calling with verbosity=0 to suppress detailed output
            # The sync_whoop command returns its own detailed logs
            # Here we just report success/failure

            return {
                'success': True,
                'message': f'Successfully synced Whoop data (last {days} days)'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed: {str(e)}'
            }

    def _sync_withings(self, days):
        """Sync Withings weight data."""
        self.stdout.write(self.style.HTTP_INFO('\n[2/3] Syncing Withings weight measurements...'))

        try:
            # Call the sync_withings command
            call_command('sync_withings', days=days, verbosity=0)

            return {
                'success': True,
                'message': f'Successfully synced Withings data (last {days} days)'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed: {str(e)}'
            }

    def _sync_toggl(self, days):
        """Sync Toggl time entries."""
        self.stdout.write(self.style.HTTP_INFO('\n[3/3] Syncing Toggl time entries...'))

        try:
            # Call the sync_toggl command
            call_command('sync_toggl', days=days, verbosity=0)

            return {
                'success': True,
                'message': f'Successfully synced Toggl data (last {days} days)'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed: {str(e)}'
            }

    def _sync_food(self, days):
        """Sync food tracking data (placeholder for future implementation)."""
        self.stdout.write(self.style.HTTP_INFO('\n[3/3] Syncing food data...'))
        self.stdout.write(self.style.WARNING('  Food tracking not yet implemented'))
        return {
            'success': True,
            'message': 'Not yet implemented'
        }

    def _sync_fasting(self, days):
        """Sync fasting tracking data (placeholder for future implementation)."""
        self.stdout.write(self.style.HTTP_INFO('\n[4/4] Syncing fasting data...'))
        self.stdout.write(self.style.WARNING('  Fasting tracking not yet implemented'))
        return {
            'success': True,
            'message': 'Not yet implemented'
        }
