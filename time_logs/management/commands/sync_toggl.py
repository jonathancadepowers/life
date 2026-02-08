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

from time_logs.models import TimeLog
from goals.models import Goal
from projects.models import Project
from time_logs.services.toggl_client import TogglAPIClient
from datetime import datetime, timedelta, timezone
from django.utils import timezone as django_timezone
from lifetracker.sync_utils import BaseSyncCommand


def _ensure_aware(dt):
    """Make a datetime timezone-aware if it is naive."""
    if django_timezone.is_naive(dt):
        return django_timezone.make_aware(dt)
    return dt


def _parse_iso_datetime(value):
    """Parse an ISO 8601 datetime string and ensure it is timezone-aware."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _ensure_aware(dt)


class Command(BaseSyncCommand):
    help = "Sync time entries from Toggl Track"
    source_name = "Toggl"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        # Override --all description for Toggl-specific behavior
        # (already added by BaseSyncCommand, no need to re-add)

    def sync(self, days, sync_all=False):
        if sync_all:
            days = 365

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("  TOGGL TIME ENTRY SYNC"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Syncing last {days} days of time entries...\n")

        try:
            client = TogglAPIClient()
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            self.stdout.write(f"Date range: {start_date.date()} to {end_date.date()}")

            self.stdout.write("Fetching projects from Toggl...")
            toggl_projects = client.get_projects()
            project_names = {p["id"]: p["name"] for p in toggl_projects}

            self.stdout.write("Fetching tags from Toggl...")
            toggl_tags = client.get_tags()
            tag_name_to_id = {tag["name"]: str(tag["id"]) for tag in toggl_tags}

            self.stdout.write("Fetching time entries from Toggl...")
            time_entries = client.get_time_entries(start_date=start_date, end_date=end_date)
            self.stdout.write(f"Found {len(time_entries)} time entries\n")

            counts = {"created": 0, "updated": 0, "skipped": 0}
            for entry in time_entries:
                result = self._process_entry(entry, project_names, tag_name_to_id)
                counts[result] += 1

            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("  SYNC SUMMARY"))
            self.stdout.write("=" * 60)
            self.stdout.write(self.style.SUCCESS(f'\u2713 Created: {counts["created"]}'))
            self.stdout.write(self.style.WARNING(f'\u21bb Updated: {counts["updated"]}'))
            self.stdout.write(f'\u2298 Skipped: {counts["skipped"]}')
            self.stdout.write("=" * 60)

            return self.make_result(
                created=counts["created"],
                updated=counts["updated"],
                skipped=counts["skipped"],
            )

        except ValueError as e:
            self.stdout.write(self.style.ERROR(f"\n\u2717 Configuration Error: {str(e)}"))
            self.stdout.write(self.style.WARNING("\nMake sure to set:"))
            self.stdout.write("  TOGGL_API_TOKEN=your-api-token")
            self.stdout.write("  TOGGL_WORKSPACE_ID=your-workspace-id")
            return self.make_error_result(str(e), auth_error=True)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n\u2717 Error: {str(e)}"))
            return self.make_error_result(str(e))

    def _process_entry(self, entry, project_names, tag_name_to_id):
        """Process a single Toggl time entry. Returns 'created', 'updated', or 'skipped'."""
        toggl_entry_id = entry.get("id")
        start = entry.get("start")
        stop = entry.get("stop")
        toggl_project_id = entry.get("project_id")
        entry_tags = entry.get("tags", [])

        # Must have end time and project; tags are optional
        if not toggl_entry_id or not start or not stop or not toggl_project_id:
            return "skipped"

        start_dt = _parse_iso_datetime(start)
        end_dt = _parse_iso_datetime(stop)

        # Auto-create Project if needed
        if toggl_project_id in project_names:
            Project.objects.get_or_create(
                project_id=toggl_project_id, defaults={"display_string": project_names[toggl_project_id]}
            )

        # Auto-create Goals for each tag
        goal_objects = self._resolve_goals(entry_tags, tag_name_to_id)

        # Create or update time log
        time_log, created_flag = TimeLog.objects.update_or_create(
            source="Toggl",
            source_id=str(toggl_entry_id),
            defaults={
                "start": start_dt,
                "end": end_dt,
                "project_id": toggl_project_id,
            },
        )
        time_log.goals.set(goal_objects)

        return "created" if created_flag else "updated"

    def _resolve_goals(self, entry_tags, tag_name_to_id):
        """Resolve Toggl tag names to Goal objects, creating them as needed."""
        goal_objects = []
        for tag_name in entry_tags:
            if not tag_name or tag_name not in tag_name_to_id:
                continue
            tag_id = tag_name_to_id[tag_name]
            goal, _ = Goal.objects.update_or_create(goal_id=tag_id, defaults={"display_string": tag_name})
            goal_objects.append(goal)
        return goal_objects
