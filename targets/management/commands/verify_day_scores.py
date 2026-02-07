"""
Management command to verify that all day_scores are correctly calculated.
"""
from django.core.management.base import BaseCommand
from targets.models import DailyAgenda


class Command(BaseCommand):
    help = 'Verify that all day_scores are correctly calculated based on targets 1-3'

    def handle(self, *_args, **_options):
        total_records = 0
        incorrect_records = 0
        errors = []

        for agenda in DailyAgenda.objects.all():
            total_records += 1

            # Calculate expected day_score
            targets_set = 0
            total_score = 0

            for i in range(1, 4):
                target = getattr(agenda, f'target_{i}')
                target_score = getattr(agenda, f'target_{i}_score')

                if target:
                    targets_set += 1
                    if target_score is not None:
                        total_score += target_score

            # Calculate expected day score
            if targets_set > 0:
                expected_score = total_score / targets_set
            else:
                expected_score = None

            # Compare with actual day_score
            actual_score = agenda.day_score

            # Check if they match (with floating point tolerance)
            if expected_score is None and actual_score is None:
                # Both None - correct
                pass
            elif expected_score is None or actual_score is None:
                # One is None, other is not - incorrect
                incorrect_records += 1
                errors.append({
                    'id': agenda.id,
                    'date': agenda.date,
                    'expected': expected_score,
                    'actual': actual_score,
                    'targets': [
                        f"T1: {agenda.target_1} ({agenda.target_1_score})",
                        f"T2: {agenda.target_2} ({agenda.target_2_score})",
                        f"T3: {agenda.target_3} ({agenda.target_3_score})",
                    ]
                })
            elif abs(expected_score - actual_score) > 0.0001:
                # Scores don't match - incorrect
                incorrect_records += 1
                errors.append({
                    'id': agenda.id,
                    'date': agenda.date,
                    'expected': expected_score,
                    'actual': actual_score,
                    'targets': [
                        f"T1: {agenda.target_1} ({agenda.target_1_score})",
                        f"T2: {agenda.target_2} ({agenda.target_2_score})",
                        f"T3: {agenda.target_3} ({agenda.target_3_score})",
                    ]
                })

        # Print results
        self.stdout.write(self.style.SUCCESS('\n=== Day Score Verification Results ==='))
        self.stdout.write(f'Total records checked: {total_records}')
        self.stdout.write(f'Correct records: {total_records - incorrect_records}')
        self.stdout.write(f'Incorrect records: {incorrect_records}')

        if incorrect_records > 0:
            self.stdout.write(self.style.ERROR('\n=== Errors Found ==='))
            for error in errors[:10]:  # Show first 10 errors
                self.stdout.write(f"\nID: {error['id']}, Date: {error['date']}")
                self.stdout.write(f"  Expected: {error['expected']}")
                self.stdout.write(f"  Actual: {error['actual']}")
                for target in error['targets']:
                    self.stdout.write(f"  {target}")

            if len(errors) > 10:
                self.stdout.write(f"\n... and {len(errors) - 10} more errors")
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ All day_scores are correctly calculated!'))
