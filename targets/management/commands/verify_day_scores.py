"""
Management command to verify that all day_scores are correctly calculated.
"""
from django.core.management.base import BaseCommand
from targets.models import DailyAgenda


def _compute_expected_score(agenda):
    """Calculate the expected day_score from targets 1-3. Returns float or None."""
    targets_set = 0
    total_score = 0

    for i in range(1, 4):
        target = getattr(agenda, f'target_{i}')
        target_score = getattr(agenda, f'target_{i}_score')

        if target:
            targets_set += 1
            if target_score is not None:
                total_score += target_score

    if targets_set > 0:
        return total_score / targets_set
    return None


def _scores_match(expected, actual):
    """Return True if expected and actual scores are considered equal."""
    if expected is None and actual is None:
        return True
    if expected is None or actual is None:
        return False
    return abs(expected - actual) <= 0.0001


def _build_error_record(agenda, expected_score, actual_score):
    """Build a dict describing a score mismatch for reporting."""
    return {
        'id': agenda.id,
        'date': agenda.date,
        'expected': expected_score,
        'actual': actual_score,
        'targets': [
            f"T1: {agenda.target_1} ({agenda.target_1_score})",
            f"T2: {agenda.target_2} ({agenda.target_2_score})",
            f"T3: {agenda.target_3} ({agenda.target_3_score})",
        ]
    }


class Command(BaseCommand):
    help = 'Verify that all day_scores are correctly calculated based on targets 1-3'

    def handle(self, *_args, **_options):
        errors = []

        for agenda in DailyAgenda.objects.all():
            expected_score = _compute_expected_score(agenda)
            if not _scores_match(expected_score, agenda.day_score):
                errors.append(_build_error_record(agenda, expected_score, agenda.day_score))

        total_records = DailyAgenda.objects.count()
        incorrect_records = len(errors)

        # Print results
        self.stdout.write(self.style.SUCCESS('\n=== Day Score Verification Results ==='))
        self.stdout.write(f'Total records checked: {total_records}')
        self.stdout.write(f'Correct records: {total_records - incorrect_records}')
        self.stdout.write(f'Incorrect records: {incorrect_records}')

        if incorrect_records > 0:
            self._print_errors(errors)
        else:
            self.stdout.write(self.style.SUCCESS('\n\u2713 All day_scores are correctly calculated!'))

    def _print_errors(self, errors):
        """Print up to 10 error records."""
        self.stdout.write(self.style.ERROR('\n=== Errors Found ==='))
        for error in errors[:10]:
            self.stdout.write(f"\nID: {error['id']}, Date: {error['date']}")
            self.stdout.write(f"  Expected: {error['expected']}")
            self.stdout.write(f"  Actual: {error['actual']}")
            for target in error['targets']:
                self.stdout.write(f"  {target}")

        if len(errors) > 10:
            self.stdout.write(f"\n... and {len(errors) - 10} more errors")
