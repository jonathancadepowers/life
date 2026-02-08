from django.test import TestCase
from goals.models import Goal


class GoalModelTests(TestCase):
    """Tests for the Goal model."""

    def test_create_goal_with_goal_id_and_display_string(self):
        """Create goal with goal_id (CharField PK) and display_string."""
        goal = Goal.objects.create(
            goal_id='tag-123',
            display_string='Exercise Daily',
        )
        self.assertEqual(goal.goal_id, 'tag-123')
        self.assertEqual(goal.display_string, 'Exercise Daily')
        self.assertEqual(goal.pk, 'tag-123')

    def test_str_returns_display_string_with_id(self):
        """__str__ returns 'display_string (ID: goal_id)'."""
        goal = Goal.objects.create(
            goal_id='tag-456',
            display_string='Read More',
        )
        self.assertEqual(str(goal), 'Read More (ID: tag-456)')

    def test_ordering_by_display_string(self):
        """Goals are ordered by display_string."""
        Goal.objects.create(goal_id='z-goal', display_string='Zzz Sleep')
        Goal.objects.create(goal_id='a-goal', display_string='Alpha Goal')
        Goal.objects.create(goal_id='m-goal', display_string='Meditate')

        goals = list(Goal.objects.values_list('display_string', flat=True))
        self.assertEqual(goals, ['Alpha Goal', 'Meditate', 'Zzz Sleep'])
