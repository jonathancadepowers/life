from django.core.management.base import BaseCommand
from django.db import connection
from monthly_objectives.models import MonthlyObjective


class Command(BaseCommand):
    help = 'Update the result field for all monthly objectives by executing their SQL queries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--objective-id',
            type=str,
            help='Update only a specific objective by its objective_id',
        )

    def handle(self, *_args, **options):
        objective_id = options.get('objective_id')

        if objective_id:
            objectives = MonthlyObjective.objects.filter(objective_id=objective_id)
            if not objectives.exists():
                self.stdout.write(self.style.ERROR(f'No objective found with ID: {objective_id}'))
                return
        else:
            objectives = MonthlyObjective.objects.all()

        updated_count = 0
        error_count = 0

        for obj in objectives:
            try:
                # Execute the SQL query
                with connection.cursor() as cursor:
                    cursor.execute(obj.objective_definition)
                    row = cursor.fetchone()

                    if row and row[0] is not None:
                        result = float(row[0])
                    else:
                        result = 0.0

                # Update the result field
                obj.result = result
                obj.save(update_fields=['result'])

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Updated {obj.objective_id}: {obj.label} = {result}'
                    )
                )
                updated_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Error updating {obj.objective_id}: {obj.label} - {str(e)}'
                    )
                )
                error_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nComplete! Updated {updated_count} objective(s), {error_count} error(s)'
            )
        )
