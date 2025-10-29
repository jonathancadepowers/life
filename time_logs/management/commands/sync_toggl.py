"""
Django management command to sync time entries from Toggl.

This command fetches time entries from Toggl Track and stores them in the TimeLog model.

Mapping:
- Toggl Projects → Database Projects
- Toggl Tags → Database Goals (many-to-many)

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

            # Fetch Toggl projects for auto-creation
            self.stdout.write('Fetching projects from Toggl...')
            toggl_projects = client.get_projects()

            # Build lookup dictionary for project names
            project_names = {p['id']: p['name'] for p in toggl_projects}

            # Fetch Toggl tags for auto-creation (Goals in our database)
            self.stdout.write('Fetching tags from Toggl...')
            toggl_tags = client.get_tags()

            # Build lookup dictionary: tag name -> tag ID
            # This allows us to map tag names (returned in time entries) to tag IDs
            tag_name_to_id = {tag['name']: str(tag['id']) for tag in toggl_tags}

            # Fetch time entries
            self.stdout.write('Fetching time entries from Toggl...')
            time_entries = client.get_time_entries(
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
                toggl_project_id = entry.get('project_id')  # Toggl Project → DB Project
                entry_tags = entry.get('tags', [])  # Toggl Tags → DB Goals (array)

                # Skip entries without required fields: must have end time and project
                # Tags are optional
                if not toggl_entry_id or not start or not stop or not toggl_project_id:
                    skipped += 1
                    continue

                # Parse datetime strings (Toggl returns ISO 8601 UTC)
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(stop.replace('Z', '+00:00'))

                # Make datetimes timezone-aware if needed
                if django_timezone.is_naive(start_dt):
                    start_dt = django_timezone.make_aware(start_dt)
                if django_timezone.is_naive(end_dt):
                    end_dt = django_timezone.make_aware(end_dt)

                # Auto-create Project if needed (Toggl Project → DB Project)
                if toggl_project_id and toggl_project_id in project_names:
                    Project.objects.get_or_create(
                        project_id=toggl_project_id,
                        defaults={'display_string': project_names[toggl_project_id]}
                    )

                # Auto-create Goals for each tag (Toggl Tags → DB Goals)
                # Time entries return tag names, but we need to use tag IDs as primary keys
                # to handle tag renames correctly
                goal_objects = []
                for tag_name in entry_tags:
                    if tag_name and tag_name in tag_name_to_id:
                        tag_id = tag_name_to_id[tag_name]
                        goal, _ = Goal.objects.update_or_create(
                            goal_id=tag_id,  # Use Toggl tag ID as primary key
                            defaults={'display_string': tag_name}
                        )
                        goal_objects.append(goal)

                # Create or update time log
                time_log, created_flag = TimeLog.objects.update_or_create(
                    source='Toggl',
                    source_id=str(toggl_entry_id),
                    defaults={
                        'start': start_dt,
                        'end': end_dt,
                        'project_id': toggl_project_id,  # Toggl Project → DB Project
                    }
                )

                # Set the ManyToMany relationship for goals
                time_log.goals.set(goal_objects)

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
