# Migration to recalculate all day_scores after removing other_plans_score

from django.db import migrations


def recalculate_day_scores(apps, schema_editor):
    """
    Recalculate day_score for all DailyAgenda records.
    Now only considers targets 1-3, not other_plans.
    """
    DailyAgenda = apps.get_model('targets', 'DailyAgenda')

    for agenda in DailyAgenda.objects.all():
        targets_set = 0
        total_score = 0

        # Check targets 1-3
        for i in range(1, 4):
            target = getattr(agenda, f'target_{i}')
            target_score = getattr(agenda, f'target_{i}_score')

            # Target is set if it exists
            if target:
                targets_set += 1
                # Add score if it exists (0, 0.5, or 1)
                if target_score is not None:
                    total_score += target_score

        # Calculate day score if any targets are set (excluding other_plans)
        if targets_set > 0:
            agenda.day_score = total_score / targets_set
        else:
            agenda.day_score = None

        agenda.save()


def reverse_recalculate(apps, schema_editor):
    """
    Reverse migration - we can't restore the old scores since we don't have
    other_plans_score anymore, so this is a no-op.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('targets', '0011_remove_dailyagenda_other_plans_score'),
    ]

    operations = [
        migrations.RunPython(recalculate_day_scores, reverse_recalculate),
    ]
