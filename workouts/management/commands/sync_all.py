"""
Django management command to sync all data sources.

This master sync command orchestrates syncing data from all configured sources:
- Whoop workouts
- Withings weight measurements
- Cronometer nutrition data

Usage:
    python manage.py sync_all [--days=30]

This command is ideal for scheduled jobs (cron, etc.)

After running, access structured results via `cmd.sync_results` — a dict
mapping source names to SyncResult objects. This is used by the master_sync
AJAX view to avoid fragile string parsing of command output.
"""
from django.core.management.base import BaseCommand
from datetime import datetime

from lifetracker.sync_utils import SyncResult


class Command(BaseCommand):
    help = 'Sync data from all configured sources (Whoop, Withings, Cronometer)'

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

    def handle(self, *_args, **options):
        days = options['days']
        whoop_only = options['whoop_only']

        start_time = datetime.now()

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  LIFE TRACKER - MASTER SYNC'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Started at: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write(f'Syncing last {days} days of data...\n')

        # Structured results accessible after execution
        self.sync_results = {}

        # Sync Whoop workouts
        self.stdout.write(self.style.HTTP_INFO('\n[1/3] Syncing Whoop workouts...'))
        self.sync_results['whoop'] = self._run_sync_command(
            'workouts.management.commands.sync_whoop', days
        )

        if not whoop_only:
            # Sync Withings weight measurements
            self.stdout.write(self.style.HTTP_INFO('\n[2/3] Syncing Withings weight measurements...'))
            self.sync_results['withings'] = self._run_sync_command(
                'weight.management.commands.sync_withings', days
            )

            # Sync Cronometer nutrition data
            self.stdout.write(self.style.HTTP_INFO('\n[3/3] Syncing Cronometer nutrition data...'))
            self.sync_results['cronometer'] = self._run_sync_command(
                'nutrition.management.commands.sync_cronometer', days
            )

        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('  SYNC SUMMARY'))
        self.stdout.write('=' * 60)

        for source, result in self.sync_results.items():
            if result.success:
                self.stdout.write(self.style.SUCCESS(
                    f'✓ {source.upper()}: {result.summary}'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f'✗ {source.upper()}: {result.summary}'
                ))

        self.stdout.write(f'\nCompleted in {duration:.1f} seconds')
        self.stdout.write('=' * 60)

    def _run_sync_command(self, module_path, days):
        """
        Import and run a sync command's sync() method directly,
        returning its SyncResult.

        Falls back to a failed SyncResult if the command raises.
        """
        try:
            from importlib import import_module
            module = import_module(module_path)
            cmd = module.Command()
            cmd.stdout = self.stdout
            cmd.style = self.style
            return cmd.sync(days)
        except Exception as e:
            source = module_path.split('.')[-1].replace('sync_', '')
            return SyncResult(
                source=source,
                success=False,
                error_message=str(e),
            )
