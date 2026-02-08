# Generated manually to transition from column_name PK to id PK
from django.db import migrations, models


def populate_id_field(apps, _schema_editor):
    """Populate the new id field with sequential values"""
    LifeTrackerColumn = apps.get_model('settings', 'LifeTrackerColumn')
    for index, column in enumerate(LifeTrackerColumn.objects.all().order_by('column_name'), start=1):
        column.id = index
        column.save(update_fields=['id'])


def reverse_populate_id_field(_apps, _schema_editor):
    """Reverse migration - nothing to do since we're removing the id field"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0005_lifetrackercolumn_end_date_and_more'),
    ]

    operations = [
        # Step 1: Add id field (nullable, not primary key yet)
        migrations.AddField(
            model_name='lifetrackercolumn',
            name='id',
            field=models.IntegerField(null=True),
        ),
        # Step 2: Populate id field with sequential values
        migrations.RunPython(populate_id_field, reverse_populate_id_field),
        # Step 3+4: Swap primary key from column_name to id in one operation.
        # These MUST be combined with SeparateDatabaseAndState because SQLite
        # rebuilds tables on ALTER. If we remove PK from column_name first
        # (without id being PK yet), Django auto-adds an id field during the
        # rebuild, conflicting with the id we added in Step 1.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='lifetrackercolumn',
                    name='column_name',
                    field=models.CharField(help_text="Internal name of the column (e.g., 'run', 'fast', 'strength')", max_length=50, unique=True),
                ),
                migrations.AlterField(
                    model_name='lifetrackercolumn',
                    name='id',
                    field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
                ),
            ],
            database_operations=[
                # On PostgreSQL (production): these columns were already altered
                # by the original migration. On SQLite (test DB): the table
                # rebuild handles both changes atomically since the state now
                # shows id as PK and column_name as non-PK simultaneously.
                migrations.AlterField(
                    model_name='lifetrackercolumn',
                    name='id',
                    field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
                ),
                migrations.AlterField(
                    model_name='lifetrackercolumn',
                    name='column_name',
                    field=models.CharField(help_text="Internal name of the column (e.g., 'run', 'fast', 'strength')", max_length=50, unique=True),
                ),
            ],
        ),
    ]
