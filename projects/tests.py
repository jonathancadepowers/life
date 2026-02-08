from django.test import TestCase
from projects.models import Project


class ProjectModelTests(TestCase):
    """Tests for the Project model."""

    def test_create_project_with_project_id_and_display_string(self):
        """Create project with project_id (IntegerField PK) and display_string."""
        project = Project.objects.create(
            project_id=12345,
            display_string='Life Tracker',
        )
        self.assertEqual(project.project_id, 12345)
        self.assertEqual(project.display_string, 'Life Tracker')
        self.assertEqual(project.pk, 12345)

    def test_str_returns_display_string(self):
        """__str__ returns display_string."""
        project = Project.objects.create(
            project_id=67890,
            display_string='Side Project',
        )
        self.assertEqual(str(project), 'Side Project')

    def test_ordering_by_display_string(self):
        """Projects are ordered by display_string."""
        Project.objects.create(project_id=3, display_string='Zebra')
        Project.objects.create(project_id=1, display_string='Alpha')
        Project.objects.create(project_id=2, display_string='Middle')

        projects = list(Project.objects.values_list('display_string', flat=True))
        self.assertEqual(projects, ['Alpha', 'Middle', 'Zebra'])
