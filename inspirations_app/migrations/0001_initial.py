# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Inspiration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(help_text='Upload an image (book cover, album art, movie poster, etc.)', upload_to='inspirations/')),
                ('flip_text', models.CharField(help_text='Text to display when image is flipped (1-2 sentences)', max_length=200)),
                ('type', models.CharField(help_text="Type of inspiration (e.g., 'Book', 'Film', 'Album', 'TV Show')", max_length=50)),
                ('order', models.PositiveIntegerField(default=0, help_text='Display order (lower numbers appear first)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Inspiration',
                'verbose_name_plural': 'Inspirations',
                'ordering': ['order', 'created_at'],
            },
        ),
    ]
