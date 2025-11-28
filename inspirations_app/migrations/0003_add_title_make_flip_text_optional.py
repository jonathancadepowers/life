# Add title field and make flip_text optional

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inspirations_app', '0002_remove_inspiration_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='inspiration',
            name='title',
            field=models.CharField(blank=True, help_text='Title of the work (e.g., book title, film name, album name)', max_length=200),
        ),
        migrations.AlterField(
            model_name='inspiration',
            name='flip_text',
            field=models.CharField(blank=True, help_text='Text to display when image is flipped (1-2 sentences)', max_length=200),
        ),
    ]
