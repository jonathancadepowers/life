"""
Shared sync infrastructure for management commands.

SyncResult — structured return type for all sync commands.
BaseSyncCommand — optional base class with --days/--all args and result tracking.
"""

from dataclasses import dataclass
from django.core.management.base import BaseCommand


@dataclass
class SyncResult:
    """Structured result from a sync operation."""

    source: str
    success: bool = True
    created: int = 0
    updated: int = 0
    skipped: int = 0
    error_message: str = ""
    auth_error: bool = False

    @property
    def total(self):
        return self.created + self.updated + self.skipped

    @property
    def summary(self):
        if not self.success:
            return f"Failed: {self.error_message}"
        parts = []
        if self.created:
            parts.append(f"{self.created} created")
        if self.updated:
            parts.append(f"{self.updated} updated")
        if self.skipped:
            parts.append(f"{self.skipped} skipped")
        return ", ".join(parts) if parts else "No records processed"


class BaseSyncCommand(BaseCommand):
    """
    Base class for data sync management commands.

    Provides:
    - --days and --all arguments
    - Counting helpers (self.counts dict)
    - self.sync_result for structured result access after handle()

    Subclasses should override `sync(days, sync_all)` and return a SyncResult.
    """

    # Subclasses set this to their source name (e.g., 'Whoop', 'Withings')
    source_name = ""

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=30, help="Number of days in the past to sync data from (default: 30)"
        )
        parser.add_argument("--all", action="store_true", help="Sync all available data (ignores --days parameter)")

    def handle(self, *_args, **options):
        days = options["days"]
        sync_all = options.get("all", False)
        self.sync_result = self.sync(days, sync_all)

    def sync(self, days, sync_all=False):
        """Override in subclasses. Must return a SyncResult."""
        raise NotImplementedError

    def make_result(self, **kwargs):
        """Convenience: create a SyncResult pre-filled with self.source_name."""
        return SyncResult(source=self.source_name, **kwargs)

    def make_error_result(self, message, auth_error=False):
        """Create a failed SyncResult."""
        return SyncResult(
            source=self.source_name,
            success=False,
            error_message=message,
            auth_error=auth_error,
        )
