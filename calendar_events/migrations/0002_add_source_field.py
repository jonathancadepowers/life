# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendar_events', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='source',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
