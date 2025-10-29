# Generated migration to convert Goal primary keys from tag names to tag IDs

from django.db import migrations
import os


def convert_goal_names_to_ids(apps, schema_editor):
    """
    Convert existing Goal records from using tag names as IDs to using tag IDs.

    This is necessary to handle tag renames in Toggl correctly. When a tag is renamed,
    the tag ID stays the same but the name changes. If we use names as primary keys,
    a rename would create a duplicate goal.
    """
    Goal = apps.get_model('goals', 'Goal')
    TimeLog = apps.get_model('time_logs', 'TimeLog')

    # Only proceed if there are goals to migrate
    existing_goals = list(Goal.objects.all())
    if not existing_goals:
        print("No goals to migrate.")
        return

    # Check if we can connect to Toggl API
    try:
        from time_logs.services.toggl_client import TogglAPIClient
        client = TogglAPIClient()
        toggl_tags = client.get_tags()
    except Exception as e:
        print(f"Warning: Could not fetch tags from Toggl API: {e}")
        print("Skipping migration. Run this migration again after fixing Toggl API access.")
        return

    # Build mapping: tag name -> tag ID
    tag_name_to_id = {tag['name']: str(tag['id']) for tag in toggl_tags}

    # Track which goals need to be migrated
    goals_to_migrate = []
    goals_skipped = []

    for goal in existing_goals:
        # Check if this goal_id looks like a tag ID already (numeric string)
        if goal.goal_id.isdigit():
            # Already using tag ID, skip
            continue

        # Try to find the corresponding tag ID in Toggl
        if goal.goal_id in tag_name_to_id:
            tag_id = tag_name_to_id[goal.goal_id]
            goals_to_migrate.append({
                'old_goal_id': goal.goal_id,
                'new_goal_id': tag_id,
                'display_string': goal.display_string
            })
        else:
            # Tag no longer exists in Toggl or was manually created
            goals_skipped.append(goal.goal_id)
            print(f"Warning: Goal '{goal.goal_id}' not found in Toggl. Keeping as-is.")

    if not goals_to_migrate:
        print("No goals need migration.")
        return

    print(f"Migrating {len(goals_to_migrate)} goals from tag names to tag IDs...")

    # Migrate each goal
    for goal_data in goals_to_migrate:
        old_goal_id = goal_data['old_goal_id']
        new_goal_id = goal_data['new_goal_id']
        display_string = goal_data['display_string']

        # Check if a goal with the new ID already exists
        if Goal.objects.filter(goal_id=new_goal_id).exists():
            print(f"Warning: Goal with ID '{new_goal_id}' already exists. Skipping '{old_goal_id}'.")
            continue

        # Get the old goal
        old_goal = Goal.objects.get(goal_id=old_goal_id)

        # Create new goal with tag ID
        new_goal = Goal.objects.create(
            goal_id=new_goal_id,
            display_string=display_string
        )

        # Update all TimeLog.goals relationships
        # Get all TimeLogs that reference the old goal
        time_logs_with_old_goal = TimeLog.objects.filter(goals=old_goal)

        for time_log in time_logs_with_old_goal:
            # Add the new goal to this time log
            time_log.goals.add(new_goal)
            # Remove the old goal from this time log
            time_log.goals.remove(old_goal)

        # Delete the old goal
        old_goal.delete()

        print(f"Migrated goal '{old_goal_id}' -> '{new_goal_id}'")

    print(f"Migration complete! Migrated {len(goals_to_migrate)} goals.")
    if goals_skipped:
        print(f"Skipped {len(goals_skipped)} goals that weren't found in Toggl.")


class Migration(migrations.Migration):

    dependencies = [
        ('goals', '0002_fix_goal_id_datatype'),
        ('time_logs', '0001_initial'),  # Need TimeLog model for relationship updates
    ]

    operations = [
        migrations.RunPython(
            convert_goal_names_to_ids,
            reverse_code=migrations.RunPython.noop
        ),
    ]
