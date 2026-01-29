from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CalendarEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('outlook_id', models.CharField(db_index=True, max_length=255, unique=True)),
                ('subject', models.CharField(max_length=500)),
                ('start', models.DateTimeField(db_index=True)),
                ('end', models.DateTimeField()),
                ('is_all_day', models.BooleanField(default=False)),
                ('location', models.CharField(blank=True, default='', max_length=500)),
                ('organizer', models.EmailField(blank=True, default='', max_length=255)),
                ('body_preview', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-start'],
            },
        ),
        migrations.AddIndex(
            model_name='calendarevent',
            index=models.Index(fields=['start', 'end'], name='calendar_ev_start_c25c7f_idx'),
        ),
    ]
