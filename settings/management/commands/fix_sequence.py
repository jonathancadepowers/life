from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Fix the auto-increment sequence for LifeTrackerColumn"

    def handle(self, *_args, **_options):
        with connection.cursor() as cursor:
            # For PostgreSQL
            if connection.vendor == "postgresql":
                cursor.execute(
                    """
                    SELECT setval(
                        pg_get_serial_sequence('settings_lifetrackercolumn', 'id'),
                        COALESCE((SELECT MAX(id) FROM settings_lifetrackercolumn), 1),
                        true
                    );
                """
                )
                result = cursor.fetchone()[0]
                self.stdout.write(self.style.SUCCESS(f"PostgreSQL sequence reset to: {result}"))

            # For SQLite, no action needed as it auto-manages sequences
            elif connection.vendor == "sqlite":
                self.stdout.write(self.style.SUCCESS("SQLite does not require sequence management"))

            else:
                self.stdout.write(self.style.WARNING(f"Unsupported database vendor: {connection.vendor}"))
