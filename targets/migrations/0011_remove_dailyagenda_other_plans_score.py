# Generated manually to remove other_plans_score field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('targets', '0010_dailyagenda_other_plans_score_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dailyagenda',
            name='other_plans_score',
        ),
    ]
