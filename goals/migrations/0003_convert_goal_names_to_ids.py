# Generated migration to convert Goal primary keys from tag names to tag IDs

from django.db import migrations


def _classify_goals(existing_goals, tag_name_to_id):
    """Classify existing goals into those needing migration and those to skip."""
    goals_to_migrate = []
    goals_skipped = []

    for goal in existing_goals:
        if goal.goal_id.isdigit():
            continue

        if goal.goal_id in tag_name_to_id:
            goals_to_migrate.append({
                'old_goal_id': goal.goal_id,
                'new_goal_id': tag_name_to_id[goal.goal_id],
                'display_string': goal.display_string
            })
        else:
            goals_skipped.append(goal.goal_id)
            print(f"Warning: Goal '{goal.goal_id}' not found in Toggl. Keeping as-is.")

    return goals_to_migrate, goals_skipped


def _migrate_single_goal(goal_data, Goal, TimeLog, apps):
    """Migrate a single goal from tag name to tag ID. Returns True if migrated."""
    old_goal_id = goal_data['old_goal_id']
    new_goal_id = goal_data['new_goal_id']

    if Goal.objects.filter(goal_id=new_goal_id).exists():
        print(f"Warning: Goal with ID '{new_goal_id}' already exists. Skipping '{old_goal_id}'.")
        return False

    old_goal = Goal.objects.get(goal_id=old_goal_id)
    new_goal = Goal.objects.create(
        goal_id=new_goal_id,
        display_string=goal_data['display_string']
    )

    for time_log in TimeLog.objects.filter(goals=old_goal):
        time_log.goals.add(new_goal)
        time_log.goals.remove(old_goal)

    DailyAgenda = apps.get_model('targets', 'DailyAgenda')
    DailyAgenda.objects.filter(goal_1=old_goal).update(goal_1=new_goal)
    DailyAgenda.objects.filter(goal_2=old_goal).update(goal_2=new_goal)
    DailyAgenda.objects.filter(goal_3=old_goal).update(goal_3=new_goal)

    old_goal.delete()
    print(f"Migrated goal '{old_goal_id}' -> '{new_goal_id}'")
    return True


def convert_goal_names_to_ids(apps, _schema_editor):
    """
    Convert existing Goal records from using tag names as IDs to using tag IDs.

    This is necessary to handle tag renames in Toggl correctly. When a tag is renamed,
    the tag ID stays the same but the name changes. If we use names as primary keys,
    a rename would create a duplicate goal.
    """
    Goal = apps.get_model('goals', 'Goal')
    TimeLog = apps.get_model('time_logs', 'TimeLog')

    existing_goals = list(Goal.objects.all())
    if not existing_goals:
        print("No goals to migrate.")
        return

    try:
        from time_logs.services.toggl_client import TogglAPIClient
        client = TogglAPIClient()
        toggl_tags = client.get_tags()
    except Exception as e:
        print(f"Warning: Could not fetch tags from Toggl API: {e}")
        print("Skipping migration. Run this migration again after fixing Toggl API access.")
        return

    tag_name_to_id = {tag['name']: str(tag['id']) for tag in toggl_tags}
    goals_to_migrate, goals_skipped = _classify_goals(existing_goals, tag_name_to_id)

    if not goals_to_migrate:
        print("No goals need migration.")
        return

    print(f"Migrating {len(goals_to_migrate)} goals from tag names to tag IDs...")

    for goal_data in goals_to_migrate:
        _migrate_single_goal(goal_data, Goal, TimeLog, apps)

    print(f"Migration complete! Migrated {len(goals_to_migrate)} goals.")
    if goals_skipped:
        print(f"Skipped {len(goals_skipped)} goals that weren't found in Toggl.")


class Migration(migrations.Migration):

    dependencies = [
        ('goals', '0002_fix_goal_id_datatype'),
        ('time_logs', '0001_initial'),  # Need TimeLog model for relationship updates
        ('targets', '0008_clean_target_timestamps'),  # Need DailyAgenda model for FK updates
    ]

    operations = [
        migrations.RunPython(
            convert_goal_names_to_ids,
            reverse_code=migrations.RunPython.noop
        ),
    ]
