from django.core.management.base import BaseCommand
from monthly_objectives.models import MonthlyObjective
from datetime import date


class Command(BaseCommand):
    help = 'Display all November 2025 objectives with descriptions and SQL queries'

    def handle(self, *args, **options):
        objectives = MonthlyObjective.objects.filter(
            start__gte=date(2025, 11, 1),
            end__lte=date(2025, 11, 30)
        ).order_by('label')

        self.stdout.write(f"\nFound {objectives.count()} objectives for November 2025:\n")
        self.stdout.write("=" * 100)

        for obj in objectives:
            self.stdout.write(f"\n\nObjective ID: {obj.objective_id}")
            self.stdout.write(f"Label: {obj.label}")
            self.stdout.write(f"Target: {obj.objective_value} {obj.unit_of_measurement or ''}")
            self.stdout.write("\nDescription:")
            self.stdout.write(f"  {obj.description}")
            self.stdout.write("\nSQL Query:")
            self.stdout.write(f"  {obj.objective_definition}")
            self.stdout.write("=" * 100)
