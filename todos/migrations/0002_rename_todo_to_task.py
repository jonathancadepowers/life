from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('todos', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ToDo',
            new_name='Task',
        ),
        migrations.AlterModelOptions(
            name='task',
            options={'ordering': ['-created_at']},
        ),
    ]
