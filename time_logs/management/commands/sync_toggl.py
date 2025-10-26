"""
Django management command to sync time entries from Toggl.

This command fetches time entries from Toggl Track and stores them in the TimeLog model.
Toggl Projects map to Goals, and Toggl Clients map to Projects in our database.

Usage:
    python manage.py sync_toggl [--days=30]
    python manage.py sync_toggl --all
"""
from django.core.management.base import BaseCommand
from time_logs.models import TimeLog
from goals.models import Goal
from projects.models import Project
from time_logs.services.toggl_client import TogglAPIClient
from datetime import datetime, timedelta
from django.utils import timezone as django_timezone


class Command(BaseCommand):
    help = 'Sync time entries from Toggl Track'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days in the past to sync (default: 30)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync all time entries (last 365 days)'
        )

    def handle(self, *args, **options):
        days = 365 if options['all'] else options['days']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  TOGGL TIME ENTRY SYNC'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Syncing last {days} days of time entries...\n')

        try:
            # Initialize Toggl client
            client = TogglAPIClient()

            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            self.stdout.write(f'Date range: {start_date.date()} to {end_date.date()}')

            # Fetch and cache Toggl projects and clients for auto-creation
            self.stdout.write('Fetching projects and clients from Toggl...')
            toggl_projects = client.get_projects()
            toggl_clients = client.get_clients()

            # Build lookup dictionaries
            project_names = {p['id']: p['name'] for p in toggl_projects}
            client_names = {c['id']: c['name'] for c in toggl_clients}

            # Fetch time entries with client mapping
            self.stdout.write('Fetching time entries from Toggl...')
            time_entries = client.get_time_entries_with_client_mapping(
                start_date=start_date,
                end_date=end_date
            )

            self.stdout.write(f'Found {len(time_entries)} time entries\n')

            # Sync to database
            created = 0
            updated = 0
            skipped = 0

            for entry in time_entries:
                # Extract fields
                toggl_entry_id = entry.get('id')
                start = entry.get('start')
                stop = entry.get('stop')  # Note: Toggl uses 'stop' not 'end'
                toggl_project_id = entry.get('project_id')  # Maps to goal_id
                toggl_client_id = entry.get('client_id')     # Maps to project_id

                # Skip entries without required fields
                if not toggl_entry_id or not start:
                    skipped += 1
                    continue

                # Parse datetime strings (Toggl returns ISO 8601 UTC)
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = None
                if stop:
                    end_dt = datetime.fromisoformat(stop.replace('Z', '+00:00'))

                # Make datetimes timezone-aware if needed
                if django_timezone.is_naive(start_dt):
                    start_dt = django_timezone.make_aware(start_dt)
                if end_dt and django_timezone.is_naive(end_dt):
                    end_dt = django_timezone.make_aware(end_dt)

                # Auto-create Goal if needed (Toggl Project → Goal)
                if toggl_project_id and toggl_project_id in project_names:
                    Goal.objects.get_or_create(
                        goal_id=toggl_project_id,
                        defaults={'display_string': project_names[toggl_project_id]}
                    )

                # Auto-create Project if needed (Toggl Client → Project)
                if toggl_client_id and toggl_client_id in client_names:
                    Project.objects.get_or_create(
                        project_id=toggl_client_id,
                        defaults={'display_string': client_names[toggl_client_id]}
                    )

                # Create or update time log
                time_log, created_flag = TimeLog.objects.update_or_create(
                    source='Toggl',
                    source_id=str(toggl_entry_id),
                    defaults={
                        'start': start_dt,
                        'end': end_dt,
                        'goal_id': toggl_project_id,      # Toggl Project → Goal
                        'project_id': toggl_client_id,    # Toggl Client → Project
                    }
                )

                if created_flag:
                    created += 1
                else:
                    updated += 1

            # Summary
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('  SYNC SUMMARY'))
            self.stdout.write('=' * 60)
            self.stdout.write(self.style.SUCCESS(f'✓ Created: {created}'))
            self.stdout.write(self.style.WARNING(f'↻ Updated: {updated}'))
            self.stdout.write(f'⊘ Skipped: {skipped}')
            self.stdout.write('=' * 60)

        except ValueError as e:
            # Configuration error - re-raise so sync_all can report it
            self.stdout.write(self.style.ERROR(f'\n✗ Configuration Error: {str(e)}'))
            self.stdout.write(self.style.WARNING('\nMake sure to set:'))
            self.stdout.write('  TOGGL_API_TOKEN=your-api-token')
            self.stdout.write('  TOGGL_WORKSPACE_ID=your-workspace-id')
            raise
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Error: {str(e)}'))
            raise
