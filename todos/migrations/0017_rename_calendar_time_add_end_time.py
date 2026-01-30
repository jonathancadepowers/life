from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('todos', '0016_add_calendar_time'),
    ]

    operations = [
        migrations.RenameField(
            model_name='task',
            old_name='calendar_time',
            new_name='calendar_start_time',
        ),
        migrations.AddField(
            model_name='task',
            name='calendar_end_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
