# Migration to add icon field and populate existing habits
from django.db import migrations, models


def populate_icons(apps, _schema_editor):
    """Populate icon field for existing habits based on their column_name"""
    LifeTrackerColumn = apps.get_model('settings', 'LifeTrackerColumn')

    # Map column names to their Bootstrap icon classes
    icon_mapping = {
        'run': 'bi-activity',
        'fast': 'bi-clock-history',
        'strength': 'bi-lightning-fill',
        'eat_clean': 'bi-egg-fried',
        'write': 'bi-pencil-fill',
        'weigh_in': 'bi-speedometer',
    }

    for column in LifeTrackerColumn.objects.all():
        if column.column_name in icon_mapping:
            column.icon = icon_mapping[column.column_name]
            column.save(update_fields=['icon'])


def reverse_populate_icons(apps, _schema_editor):
    """Reverse migration - reset icons to default"""
    LifeTrackerColumn = apps.get_model('settings', 'LifeTrackerColumn')
    LifeTrackerColumn.objects.all().update(icon='bi-circle')


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0006_add_id_primary_key'),
    ]

    operations = [
        # Add icon field with default value
        migrations.AddField(
            model_name='lifetrackercolumn',
            name='icon',
            field=models.CharField(default='bi-circle', help_text="Bootstrap icon class (e.g., 'bi-activity', 'bi-clock-history')", max_length=50),
        ),
        # Populate icons for existing habits
        migrations.RunPython(populate_icons, reverse_populate_icons),
    ]
