# Remove order field from Inspiration model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inspirations_app', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='inspiration',
            name='order',
        ),
    ]
