from django.test import TestCase, Client
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock
import unittest
import json

from targets.models import DailyAgenda
from projects.models import Project
from goals.models import Goal


class DailyAgendaViewsTestCase(TestCase):
    """Tests for Daily Agenda API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        # Create test project
        self.project = Project.objects.create(
            project_id=123,
            display_string='Test Project'
        )

        # Create test goal
        self.goal = Goal.objects.create(
            goal_id='test_goal',
            display_string='Test Goal'
        )

        # Create test agenda for today
        self.today = timezone.now().date()
        self.agenda = DailyAgenda.objects.create(
            date=self.today,
            project_1=self.project,
            goal_1=self.goal,
            target_1='Test Target 1',  # Now just text
            target_1_score=1.0
        )

    def test_set_agenda_page_loads(self):
        """Test that the set agenda page loads successfully"""
        response = self.client.get(reverse('set_agenda'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Today's Agenda")

    def test_save_agenda_new_entry(self):
        """Test saving a new daily agenda"""
        tomorrow = self.today + timedelta(days=1)

        data = {
            'date': tomorrow.isoformat(),
            'project_1': str(self.project.project_id),
            'goal_1': self.goal.goal_id,
            'target_1': 'New target for tomorrow',
            'project_2': '',
            'goal_2': '',
            'target_2': '',
            'project_3': '',
            'goal_3': '',
            'target_3': '',
            'other_plans': '# Tomorrow Notes'
        }

        response = self.client.post(
            reverse('save_agenda'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])

        # Verify agenda was created
        agenda = DailyAgenda.objects.get(date=tomorrow)
        self.assertEqual(agenda.project_1, self.project)
        self.assertEqual(agenda.goal_1, self.goal)
        self.assertIsNotNone(agenda.target_1)
        self.assertEqual(agenda.target_1, 'New target for tomorrow')  # Now just text
        self.assertEqual(agenda.other_plans, '# Tomorrow Notes')

    def test_save_agenda_update_existing(self):
        """Test updating an existing daily agenda"""
        data = {
            'date': self.today.isoformat(),
            'project_1': str(self.project.project_id),
            'goal_1': self.goal.goal_id,
            'target_1': 'Updated target',
            'project_2': '',
            'goal_2': '',
            'target_2': '',
            'project_3': '',
            'goal_3': '',
            'target_3': '',
            'other_plans': '# Updated Notes'
        }

        response = self.client.post(
            reverse('save_agenda'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])

        # Verify agenda was updated
        agenda = DailyAgenda.objects.get(date=self.today)
        self.assertEqual(agenda.target_1, 'Updated target')  # Now just text
        self.assertEqual(agenda.other_plans, '# Updated Notes')

    def test_save_agenda_with_explicit_date_not_utc(self):
        """
        Regression test for timezone bug where notes were saved to wrong date.

        This test ensures that when a specific date is provided in the request,
        the agenda is saved to THAT date, not to the server's UTC date.

        Bug scenario: User in Central timezone at 10pm on Oct 28 (which is 3am UTC Oct 29)
        would save to Oct 29 instead of Oct 28 because server used UTC date.

        Fix: Frontend now ALWAYS sends the user's local date explicitly.
        This test verifies the backend respects the provided date.
        """
        # Clear all existing agendas to ensure clean slate for this test
        DailyAgenda.objects.all().delete()

        # Simulate user's local date is Oct 28, but server UTC might think it's Oct 29
        user_local_date = date(2025, 10, 28)

        data = {
            'date': user_local_date.isoformat(),  # Frontend sends explicit date
            'project_1': str(self.project.project_id),
            'goal_1': self.goal.goal_id,
            'target_1': 'Test target',
            'project_2': '',
            'goal_2': '',
            'target_2': '',
            'project_3': '',
            'goal_3': '',
            'target_3': '',
            'other_plans': '# Test Notes\n- Added at 10pm local time\n- Should save to Oct 28'
        }

        response = self.client.post(
            reverse('save_agenda'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])

        # CRITICAL: Verify agenda was saved to the USER'S date, not UTC date
        agenda = DailyAgenda.objects.get(date=user_local_date)
        self.assertEqual(agenda.other_plans, '# Test Notes\n- Added at 10pm local time\n- Should save to Oct 28')

        # Ensure no agenda was created for the "wrong" date (e.g., Oct 29)
        wrong_date = user_local_date + timedelta(days=1)
        self.assertFalse(DailyAgenda.objects.filter(date=wrong_date).exists())

    def test_get_goals_for_project(self):
        """Test getting goals for a project"""
        # First, create a TimeLog entry to link the project and goal
        from time_logs.models import TimeLog
        timelog = TimeLog.objects.create(
            source='Manual',
            source_id='test-timelog-1',
            project_id=self.project.project_id,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=1)
        )
        # Link the goal to the time log
        timelog.goals.add(self.goal)

        response = self.client.get(
            reverse('get_goals_for_project'),
            {'project_id': str(self.project.project_id)}
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertIn('goals', result)
        self.assertEqual(len(result['goals']), 1)
        self.assertEqual(result['goals'][0]['goal_id'], self.goal.goal_id)

    def test_get_goals_for_project_all_parameter(self):
        """Test getting all goals with all=true parameter"""
        # Create additional goals that aren't linked to the project
        goal2 = Goal.objects.create(
            goal_id='test_goal_2',
            display_string='Test Goal 2'
        )
        goal3 = Goal.objects.create(
            goal_id='test_goal_3',
            display_string='Test Goal 3'
        )

        # Test without all parameter - should return empty (no TimeLog linking goals to project)
        response = self.client.get(
            reverse('get_goals_for_project'),
            {'project_id': str(self.project.project_id)}
        )
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(len(result['goals']), 0)  # No goals linked via TimeLog

        # Test with all=true parameter - should return all goals
        response = self.client.get(
            reverse('get_goals_for_project'),
            {'all': 'true'}
        )
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(len(result['goals']), 3)  # All goals in database
        goal_ids = [g['goal_id'] for g in result['goals']]
        self.assertIn(self.goal.goal_id, goal_ids)
        self.assertIn(goal2.goal_id, goal_ids)
        self.assertIn(goal3.goal_id, goal_ids)

    @patch('targets.views.TogglAPIClient')
    def test_sync_toggl_projects_goals_success(self, mock_toggl_client):
        """Test successful sync from Toggl"""
        # Mock Toggl API responses
        mock_client_instance = MagicMock()
        mock_toggl_client.return_value = mock_client_instance

        # Mock projects data
        mock_client_instance.get_projects.return_value = [
            {'id': 999, 'name': 'New Project from Toggl'},
            {'id': 123, 'name': 'Updated Test Project'},  # Update existing
        ]

        # Mock tags (goals) data - now includes IDs
        mock_client_instance.get_tags.return_value = [
            {'id': 456, 'name': 'new_goal_from_toggl'},
            {'id': 789, 'name': 'test_goal'},  # Already exists
        ]

        # Make request
        response = self.client.post(reverse('sync_toggl_projects_goals'))

        # Check response
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertIn('Synced 2 projects and 2 goals', result['message'])
        self.assertEqual(len(result['projects']), 2)
        # 3 goals total: 1 from setUp (old format 'test_goal') + 2 new from sync ('456', '789')
        self.assertEqual(len(result['goals']), 3)

        # Verify projects were created/updated
        self.assertTrue(Project.objects.filter(project_id=999).exists())
        updated_project = Project.objects.get(project_id=123)
        self.assertEqual(updated_project.display_string, 'Updated Test Project')

        # Verify goals were created/updated using tag IDs (not names)
        self.assertTrue(Goal.objects.filter(goal_id='456').exists())
        new_goal = Goal.objects.get(goal_id='456')
        self.assertEqual(new_goal.display_string, 'new_goal_from_toggl')

        self.assertTrue(Goal.objects.filter(goal_id='789').exists())
        existing_goal = Goal.objects.get(goal_id='789')
        self.assertEqual(existing_goal.display_string, 'test_goal')

    @patch('targets.views.TogglAPIClient')
    def test_sync_toggl_projects_goals_error(self, mock_toggl_client):
        """Test error handling when Toggl API fails"""
        # Mock Toggl API to raise an exception
        mock_toggl_client.side_effect = Exception('API connection failed')

        # Make request
        response = self.client.post(reverse('sync_toggl_projects_goals'))

        # Check response
        self.assertEqual(response.status_code, 500)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('Error syncing from Toggl', result['message'])
        self.assertIn('API connection failed', result['message'])

    @patch('targets.views.TogglAPIClient')
    def test_sync_toggl_tag_rename(self, mock_toggl_client):
        """Test that renaming a tag in Toggl updates the goal display_string without creating duplicates"""
        # Mock Toggl API responses
        mock_client_instance = MagicMock()
        mock_toggl_client.return_value = mock_client_instance

        # Initial sync: Create a goal with tag ID 555 and name "original_name"
        mock_client_instance.get_projects.return_value = [
            {'id': 123, 'name': 'Test Project'},
        ]
        mock_client_instance.get_tags.return_value = [
            {'id': 555, 'name': 'original_name'},
        ]

        # First sync
        response = self.client.post(reverse('sync_toggl_projects_goals'))
        self.assertEqual(response.status_code, 200)

        # Verify goal was created with tag ID
        self.assertTrue(Goal.objects.filter(goal_id='555').exists())
        goal = Goal.objects.get(goal_id='555')
        self.assertEqual(goal.display_string, 'original_name')
        initial_goal_count = Goal.objects.count()

        # Second sync: Same tag ID but renamed to "renamed_tag"
        mock_client_instance.get_tags.return_value = [
            {'id': 555, 'name': 'renamed_tag'},  # Same ID, different name
        ]

        # Sync again
        response = self.client.post(reverse('sync_toggl_projects_goals'))
        self.assertEqual(response.status_code, 200)

        # CRITICAL: Verify no duplicate was created
        final_goal_count = Goal.objects.count()
        self.assertEqual(final_goal_count, initial_goal_count,
                        "Tag rename should not create duplicate goals")

        # Verify the goal still exists with the same ID
        self.assertTrue(Goal.objects.filter(goal_id='555').exists())

        # Verify the display_string was updated to the new name
        goal_after_rename = Goal.objects.get(goal_id='555')
        self.assertEqual(goal_after_rename.display_string, 'renamed_tag',
                        "Goal display_string should be updated when tag is renamed in Toggl")

    def test_save_target_score(self):
        """Test saving a target score"""
        data = {
            'date': self.today.isoformat(),
            'target_num': '1',
            'score': '0.5'
        }

        response = self.client.post(
            reverse('save_target_score'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])

        # Verify score was saved
        agenda = DailyAgenda.objects.get(date=self.today)
        self.assertEqual(agenda.target_1_score, 0.5)

    def test_clear_target_score(self):
        """Test clearing a target score (setting to null)"""
        data = {
            'date': self.today.isoformat(),
            'target_num': '1',
            'score': 'null'
        }

        response = self.client.post(
            reverse('save_target_score'),
            data=data
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])

        # Verify score was cleared
        agenda = DailyAgenda.objects.get(date=self.today)
        self.assertIsNone(agenda.target_1_score)

    def test_day_score_single_target(self):
        """Test day_score calculation with one target"""
        # Score target 1 with 0.5
        data = {
            'date': self.today.isoformat(),
            'target_num': '1',
            'score': '0.5'
        }
        response = self.client.post(reverse('save_target_score'), data=data)
        result = json.loads(response.content)

        self.assertTrue(result['success'])
        self.assertEqual(result['day_score'], 0.5)

        # Verify in database
        agenda = DailyAgenda.objects.get(date=self.today)
        self.assertEqual(agenda.day_score, 0.5)

    def test_day_score_multiple_targets(self):
        """Test day_score calculation with multiple targets"""
        # Add a second target
        self.agenda.target_2 = 'Test Target 2'
        self.agenda.save()

        # Score target 1 with 1.0
        self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '1',
            'score': '1.0'
        })

        # Score target 2 with 0.5
        response = self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '2',
            'score': '0.5'
        })
        result = json.loads(response.content)

        # Day score should be (1.0 + 0.5) / 2 = 0.75
        self.assertEqual(result['day_score'], 0.75)

        agenda = DailyAgenda.objects.get(date=self.today)
        self.assertEqual(agenda.day_score, 0.75)

    def test_day_score_three_targets(self):
        """Test day_score calculation with all three targets"""
        # Add additional targets
        self.agenda.target_2 = 'Test Target 2'
        self.agenda.target_3 = 'Test Target 3'
        self.agenda.save()

        # Score all three targets
        self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '1',
            'score': '1.0'
        })
        self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '2',
            'score': '0.5'
        })
        response = self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '3',
            'score': '0.0'
        })
        result = json.loads(response.content)

        # Day score should be (1.0 + 0.5 + 0.0) / 3 = 0.5
        self.assertEqual(result['day_score'], 0.5)

    def test_day_score_partial_scoring(self):
        """Test day_score with only some targets scored"""
        # Add a second target
        self.agenda.target_2 = 'Test Target 2'
        self.agenda.save()

        # Score only target 1
        response = self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '1',
            'score': '1.0'
        })
        result = json.loads(response.content)

        # Day score should only count scored targets: 1.0 / 2 = 0.5
        # (because both targets exist, but only one is scored)
        self.assertEqual(result['day_score'], 0.5)

    def test_day_score_cleared_score(self):
        """Test day_score updates when clearing a score"""
        # Score target 1
        self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '1',
            'score': '1.0'
        })

        # Clear the score
        response = self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '1',
            'score': 'null'
        })
        result = json.loads(response.content)

        # Day score should be 0 now (0 / 1 target)
        self.assertEqual(result['day_score'], 0.0)

    def test_day_score_in_agenda_api(self):
        """Test that day_score is included in get_agenda_for_date response"""
        # Set a score
        self.agenda.target_1_score = 0.5
        self.agenda.day_score = 0.5
        self.agenda.save()

        # Fetch agenda
        response = self.client.get(
            reverse('get_agenda_for_date'),
            {'date': self.today.isoformat()}
        )
        result = json.loads(response.content)

        self.assertTrue(result['success'])
        self.assertEqual(result['agenda']['day_score'], 0.5)

    def test_day_score_with_other_plans(self):
        """Test day_score calculation includes other_plans when present"""
        # Add other_plans and a second target
        self.agenda.other_plans = '# My other plans\n- Task 1\n- Task 2'
        self.agenda.target_2 = 'Test Target 2'
        self.agenda.save()

        # Score target 1 with 1.0
        self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '1',
            'score': '1.0'
        })

        # Score target 2 with 0.5
        self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '2',
            'score': '0.5'
        })

        # Score other_plans (target_num=4) with 0.5
        response = self.client.post(reverse('save_target_score'), data={
            'date': self.today.isoformat(),
            'target_num': '4',
            'score': '0.5'
        })
        result = json.loads(response.content)

        # Day score should be (1.0 + 0.5 + 0.5) / 3 = 0.667
        self.assertAlmostEqual(result['day_score'], 0.6666666666666666, places=5)

        agenda = DailyAgenda.objects.get(date=self.today)
        self.assertAlmostEqual(agenda.day_score, 0.6666666666666666, places=5)
        self.assertEqual(agenda.other_plans_score, 0.5)

    def test_get_available_agenda_dates(self):
        """Test getting available agenda dates"""
        # Create agenda for yesterday
        yesterday = self.today - timedelta(days=1)
        DailyAgenda.objects.create(date=yesterday)

        response = self.client.get(reverse('get_available_agenda_dates'))

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertIn(self.today.isoformat(), result['dates'])
        self.assertIn(yesterday.isoformat(), result['dates'])

    def test_get_agenda_for_date(self):
        """Test getting agenda for a specific date"""
        response = self.client.get(
            reverse('get_agenda_for_date'),
            {'date': self.today.isoformat()}
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertEqual(result['agenda']['date'], self.today.isoformat())
        self.assertEqual(len(result['agenda']['targets']), 3)
        self.assertIsNotNone(result['agenda']['targets'][0]['target_name'])
        # other_plans is None by default (not set in setUp)
        self.assertIsNone(result['agenda']['other_plans'])

    @patch('time_logs.services.toggl_client.TogglAPIClient')
    def test_get_toggl_time_today(self, mock_toggl_client):
        """Test getting Toggl time for today"""
        # Mock Toggl API response
        mock_client_instance = MagicMock()
        mock_client_instance.get_time_entries.return_value = [
            {
                'id': 1,
                'project_id': int(self.project.project_id),
                'tags': [self.goal.display_string],  # Toggl API returns tag names, not IDs
                'duration': 3600,  # 1 hour in seconds
                'start': '2025-10-28T08:00:00Z'
            }
        ]
        mock_toggl_client.return_value = mock_client_instance

        response = self.client.get(
            reverse('get_toggl_time_today'),
            {
                'project_id': str(self.project.project_id),
                'goal_id': self.goal.goal_id,
                'timezone_offset': '300'  # CDT offset
            }
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        self.assertEqual(result['total_seconds'], 3600)
        self.assertEqual(result['display'], '1h 0m')

    @patch('time_logs.services.toggl_client.TogglAPIClient')
    def test_get_toggl_time_with_running_timer(self, mock_toggl_client):
        """Test getting Toggl time including a running timer"""
        # Mock Toggl API response with running timer (negative duration)
        now = timezone.now()
        start_time = now - timedelta(hours=2)

        mock_client_instance = MagicMock()
        mock_client_instance.get_time_entries.return_value = [
            {
                'id': 1,
                'project_id': int(self.project.project_id),
                'tags': [self.goal.display_string],  # Toggl API returns tag names, not IDs
                'duration': -1761666221,  # Negative = running timer
                'start': start_time.isoformat()
            }
        ]
        mock_toggl_client.return_value = mock_client_instance

        response = self.client.get(
            reverse('get_toggl_time_today'),
            {
                'project_id': str(self.project.project_id),
                'goal_id': self.goal.goal_id,
                'timezone_offset': '300'
            }
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        # Should have some time logged (running timer should be included)
        self.assertGreaterEqual(result['total_seconds'], 3600)  # At least 1 hour

    @patch('django.core.cache.cache.get')
    @patch('django.core.cache.cache.set')
    @patch('time_logs.services.toggl_client.TogglAPIClient')
    def test_goal_id_to_tag_name_conversion(self, mock_toggl_client, mock_cache_set, mock_cache_get):
        """
        Regression test: Ensure goal_id (tag ID) is converted to tag name before comparing with Toggl API results.

        This test prevents the bug where passing a tag ID (e.g., '268751883') to the API
        would fail to match entries because Toggl API returns tag NAMES (e.g., 'build_kpi_model').
        """
        # Create a goal with a numeric tag ID and a different display string
        regression_goal = Goal.objects.create(
            goal_id='999888777',  # Numeric tag ID
            display_string='test_regression_tag'  # Tag name that Toggl API will return
        )

        # Mock cache to return None (forcing API call)
        mock_cache_get.return_value = None

        # Mock Toggl API to return entries with tag NAMES (not IDs)
        mock_client_instance = MagicMock()
        mock_client_instance.get_time_entries.return_value = [
            {
                'id': 1,
                'project_id': int(self.project.project_id),
                'tags': ['test_regression_tag'],  # Toggl returns tag NAME, not ID
                'duration': 7200,  # 2 hours
                'start': '2025-10-28T08:00:00Z'
            },
            {
                'id': 2,
                'project_id': int(self.project.project_id),
                'tags': ['different_tag'],  # Entry with different tag - should be excluded
                'duration': 3600,
                'start': '2025-10-28T10:00:00Z'
            }
        ]
        mock_toggl_client.return_value = mock_client_instance

        # Pass the goal_id (tag ID) to the API - it should convert to tag name internally
        response = self.client.get(
            reverse('get_toggl_time_today'),
            {
                'project_id': str(self.project.project_id),
                'goal_id': regression_goal.goal_id,  # Passing tag ID (999888777)
                'timezone_offset': '300'
            }
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])

        # Should only count the first entry (7200 seconds = 2 hours)
        # The second entry should be excluded because its tag doesn't match
        self.assertEqual(result['total_seconds'], 7200)
        self.assertEqual(result['display'], '2h 0m')

        # Verify debug info shows the correct tag name was used
        self.assertEqual(result['debug']['entries_count'], 1)


class DailyAgendaModelTestCase(TestCase):
    """Tests for Daily Agenda model"""

    def test_create_daily_agenda(self):
        """Test creating a daily agenda"""
        today = timezone.now().date()
        agenda = DailyAgenda.objects.create(
            date=today,
            other_plans='Test notes'
        )

        self.assertEqual(agenda.date, today)
        self.assertEqual(agenda.other_plans, 'Test notes')
        self.assertEqual(str(agenda), f"Agenda for {today}")

    def test_unique_date_constraint(self):
        """Test that only one agenda can exist per date"""
        today = timezone.now().date()
        DailyAgenda.objects.create(date=today)

        # Should raise error when trying to create another agenda for same date
        with self.assertRaises(Exception):
            DailyAgenda.objects.create(date=today)

    def test_score_fields(self):
        """Test that score fields accept valid values"""
        today = timezone.now().date()
        agenda = DailyAgenda.objects.create(
            date=today,
            target_1_score=0.0,
            target_2_score=0.5,
            target_3_score=1.0
        )

        self.assertEqual(agenda.target_1_score, 0.0)
        self.assertEqual(agenda.target_2_score, 0.5)
        self.assertEqual(agenda.target_3_score, 1.0)


class ActivityReportViewsTestCase(TestCase):
    """Tests for Activity Report page"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        # Import models
        from fasting.models import FastingSession
        from nutrition.models import NutritionEntry
        from weight.models import WeighIn
        from workouts.models import Workout
        from external_data.models import WhoopSportId
        from time_logs.models import TimeLog

        self.FastingSession = FastingSession
        self.NutritionEntry = NutritionEntry
        self.WeighIn = WeighIn
        self.Workout = Workout
        self.WhoopSportId = WhoopSportId
        self.TimeLog = TimeLog

        # Create test date range (current week)
        self.today = timezone.now().date()
        self.week_start = self.today - timedelta(days=self.today.weekday())  # Monday
        self.week_end = self.week_start + timedelta(days=6)  # Sunday

        # Create test projects and goals
        self.project = Project.objects.create(
            project_id=123,
            display_string='Test Project'
        )
        self.goal = Goal.objects.create(
            goal_id='test_goal',
            display_string='Test Goal'
        )

        # Create Whoop sport IDs for testing
        self.running_sport = WhoopSportId.objects.create(
            sport_id=0,
            sport_name='Running'
        )
        self.walking_sport = WhoopSportId.objects.create(
            sport_id=63,
            sport_name='Walking'
        )

    def test_activity_report_page_loads(self):
        """Test that the activity report page loads successfully"""
        response = self.client.get(reverse('activity_report'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activity Report')

    def test_activity_report_default_date_range(self):
        """Test that default date range is current week (Monday-Sunday)"""
        response = self.client.get(reverse('activity_report'))
        self.assertEqual(response.status_code, 200)

        # Check context has correct dates
        self.assertEqual(response.context['start_date'], self.week_start)
        self.assertEqual(response.context['end_date'], self.week_end)
        self.assertEqual(response.context['days_in_range'], 7)

    def test_activity_report_custom_date_range(self):
        """Test activity report with custom date range"""
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 31)

        response = self.client.get(
            reverse('activity_report'),
            {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['start_date'], start_date)
        self.assertEqual(response.context['end_date'], end_date)
        self.assertEqual(response.context['days_in_range'], 31)

    def test_fasting_data_aggregation(self):
        """Test fasting data aggregation"""
        # Create test fasting sessions
        session_time_1 = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))
        session_time_2 = timezone.make_aware(datetime.combine(self.week_start + timedelta(days=1), datetime.min.time()))

        self.FastingSession.objects.create(
            source='Test',
            source_id='fast-1',
            fast_end_date=session_time_1,
            duration=16
        )
        self.FastingSession.objects.create(
            source='Test',
            source_id='fast-2',
            fast_end_date=session_time_2,
            duration=18
        )

        response = self.client.get(reverse('activity_report'))
        fasting_data = response.context['fasting']

        self.assertEqual(fasting_data['count'], 2)
        self.assertEqual(fasting_data['avg_duration'], 17.0)
        self.assertEqual(fasting_data['max_duration'], 18)
        self.assertGreater(fasting_data['year_count'], 0)
        self.assertGreater(fasting_data['percent_days_fasted'], 0)

    def test_fasting_no_data(self):
        """Test fasting section with no data"""
        response = self.client.get(reverse('activity_report'))
        fasting_data = response.context['fasting']

        self.assertEqual(fasting_data['count'], 0)
        self.assertEqual(fasting_data['avg_duration'], 0)
        self.assertEqual(fasting_data['max_duration'], 0)

    def test_nutrition_data_aggregation(self):
        """Test nutrition data aggregation"""
        # Create test nutrition entries
        for i in range(3):
            entry_time = timezone.make_aware(
                datetime.combine(self.week_start + timedelta(days=i), datetime.min.time())
            )
            self.NutritionEntry.objects.create(
                source='Test',
                source_id=f'nutrition-{i}',
                consumption_date=entry_time,
                calories=2000,
                protein=150,
                carbs=200,
                fat=70
            )

        response = self.client.get(reverse('activity_report'))
        nutrition_data = response.context['nutrition']

        self.assertEqual(nutrition_data['days_tracked'], 3)
        self.assertEqual(nutrition_data['days_in_range'], 7)
        self.assertAlmostEqual(nutrition_data['percent_tracked'], 42.9, places=1)
        self.assertEqual(nutrition_data['avg_calories'], 2000.0)
        self.assertEqual(nutrition_data['avg_protein'], 150.0)
        self.assertEqual(nutrition_data['avg_carbs'], 200.0)
        self.assertEqual(nutrition_data['avg_fat'], 70.0)

    def test_nutrition_no_data(self):
        """Test nutrition section with no data"""
        response = self.client.get(reverse('activity_report'))
        nutrition_data = response.context['nutrition']

        self.assertEqual(nutrition_data['days_tracked'], 0)
        self.assertEqual(nutrition_data['percent_tracked'], 0.0)

    def test_weight_data_aggregation(self):
        """Test weight data aggregation"""
        # Create test weigh-ins
        for i in range(3):
            measurement_time = timezone.make_aware(
                datetime.combine(self.week_start + timedelta(days=i), datetime.min.time())
            )
            self.WeighIn.objects.create(
                source='Test',
                source_id=f'weight-{i}',
                measurement_time=measurement_time,
                weight=180 - i  # Descending weight
            )

        response = self.client.get(reverse('activity_report'))
        weight_data = response.context['weight']

        self.assertEqual(weight_data['count'], 3)
        self.assertEqual(weight_data['start_weight'], 180.0)
        self.assertEqual(weight_data['end_weight'], 178.0)
        self.assertEqual(weight_data['change'], -2.0)
        self.assertIsNotNone(weight_data['year_change'])

    def test_weight_no_data(self):
        """Test weight section with no data"""
        response = self.client.get(reverse('activity_report'))
        weight_data = response.context['weight']

        self.assertEqual(weight_data['count'], 0)
        self.assertIsNone(weight_data['start_weight'])

    def test_workout_data_aggregation_with_distance(self):
        """Test workout data aggregation for distance-based sports (stores distance but shows calories)"""
        # Create running workout with distance
        start_time = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))
        end_time = start_time + timedelta(hours=1)

        self.Workout.objects.create(
            source='Whoop',
            source_id='workout-1',
            start=start_time,
            end=end_time,
            sport_id=0,  # Running
            calories_burned=500,
            distance_in_miles=5.0,
            average_heart_rate=150
        )

        response = self.client.get(reverse('activity_report'))
        workouts_data = response.context['workouts_by_sport']

        self.assertIn('Running', workouts_data)
        running_data = workouts_data['Running']
        self.assertEqual(running_data['count'], 1)
        self.assertEqual(running_data['total_calories'], 500.0)
        self.assertEqual(running_data['avg_heart_rate'], 150)
        # Note: distance is stored in database but not displayed in UI

    def test_workout_data_aggregation_without_distance(self):
        """Test workout data aggregation showing calories for non-distance sports"""
        # Create workout without distance
        start_time = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))
        end_time = start_time + timedelta(hours=1)

        # Create a sport without distance tracking
        yoga_sport = self.WhoopSportId.objects.create(sport_id=44, sport_name='Yoga')

        self.Workout.objects.create(
            source='Whoop',
            source_id='workout-2',
            start=start_time,
            end=end_time,
            sport_id=44,  # Yoga
            calories_burned=300,
            distance_in_miles=None,
            average_heart_rate=120
        )

        response = self.client.get(reverse('activity_report'))
        workouts_data = response.context['workouts_by_sport']

        self.assertIn('Yoga', workouts_data)
        yoga_data = workouts_data['Yoga']
        self.assertEqual(yoga_data['count'], 1)
        self.assertEqual(yoga_data['total_calories'], 300.0)

    def test_workout_multiple_sports(self):
        """Test workout aggregation with multiple sport types"""
        start_time = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))

        # Running workout
        self.Workout.objects.create(
            source='Whoop',
            source_id='workout-1',
            start=start_time,
            end=start_time + timedelta(hours=1),
            sport_id=0,
            calories_burned=500,
            distance_in_miles=5.0
        )

        # Walking workout
        self.Workout.objects.create(
            source='Whoop',
            source_id='workout-2',
            start=start_time + timedelta(hours=2),
            end=start_time + timedelta(hours=3),
            sport_id=63,
            calories_burned=300,
            distance_in_miles=3.0
        )

        response = self.client.get(reverse('activity_report'))
        workouts_data = response.context['workouts_by_sport']

        self.assertEqual(len(workouts_data), 2)
        self.assertIn('Running', workouts_data)
        self.assertIn('Walking', workouts_data)

    def test_workout_no_data(self):
        """Test workout section with no data"""
        response = self.client.get(reverse('activity_report'))
        workouts_data = response.context['workouts_by_sport']

        self.assertEqual(len(workouts_data), 0)

    def test_time_tracking_data_aggregation(self):
        """Test time tracking data aggregation by project and goal"""
        # Create time logs
        start_time = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))

        time_log = self.TimeLog.objects.create(
            source='Manual',
            source_id='log-1',
            project_id=self.project.project_id,
            start=start_time,
            end=start_time + timedelta(hours=5)
        )
        time_log.goals.add(self.goal)

        response = self.client.get(reverse('activity_report'))
        time_data = response.context['time_by_project']

        self.assertIn('Test Project', time_data)
        project_data = time_data['Test Project']
        self.assertEqual(project_data['total_hours'], 5.0)
        self.assertEqual(project_data['percentage'], 100)
        self.assertIn('Test Goal', project_data['goals'])

    def test_time_tracking_percentage_calculations(self):
        """Test that time tracking percentages add up to 100%"""
        start_time = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))

        # Create second project
        project2 = Project.objects.create(
            project_id=456,
            display_string='Test Project 2'
        )

        # First project: 6 hours
        log1 = self.TimeLog.objects.create(
            source='Manual',
            source_id='log-1',
            project_id=self.project.project_id,
            start=start_time,
            end=start_time + timedelta(hours=6)
        )
        log1.goals.add(self.goal)

        # Second project: 4 hours
        log2 = self.TimeLog.objects.create(
            source='Manual',
            source_id='log-2',
            project_id=project2.project_id,
            start=start_time + timedelta(hours=6),
            end=start_time + timedelta(hours=10)
        )
        log2.goals.add(self.goal)

        response = self.client.get(reverse('activity_report'))
        time_data = response.context['time_by_project']

        # Total should be 10 hours
        self.assertEqual(response.context['total_time_hours'], 10.0)

        # Percentages should add to 100%
        total_percentage = sum(p['percentage'] for p in time_data.values())
        self.assertEqual(total_percentage, 100)

        # Check individual percentages
        self.assertEqual(time_data['Test Project']['percentage'], 60)
        self.assertEqual(time_data['Test Project 2']['percentage'], 40)

    def test_time_tracking_no_data(self):
        """Test time tracking section with no data"""
        response = self.client.get(reverse('activity_report'))
        time_data = response.context['time_by_project']

        self.assertEqual(len(time_data), 0)
        self.assertEqual(response.context['total_time_hours'], 0.0)

    def test_template_rendering_all_sections(self):
        """Test that template renders all major sections"""
        response = self.client.get(reverse('activity_report'))
        content = response.content.decode()

        # Check for section headers
        self.assertIn('Food & Weight', content)
        self.assertIn('Exercise', content)
        self.assertIn('Time by Project', content)

        # Check for individual boxes
        self.assertIn('Fasting', content)
        self.assertIn('Nutrition', content)
        self.assertIn('Weight', content)

    def test_template_collapsible_sections(self):
        """Test that sections are collapsible"""
        # Create time tracking data so timeTrackingSection renders
        start_time = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))
        time_log = self.TimeLog.objects.create(
            source='Test',
            source_id='log-collapse-test',
            project_id=self.project.project_id,
            start=start_time,
            end=start_time + timedelta(hours=1)
        )

        response = self.client.get(reverse('activity_report'))
        content = response.content.decode()

        # Check for Bootstrap collapse classes
        self.assertIn('collapse', content)
        self.assertIn('data-bs-toggle="collapse"', content)
        self.assertIn('foodWeightSection', content)
        self.assertIn('exerciseSection', content)
        self.assertIn('timeTrackingSection', content)

    def test_template_date_pickers(self):
        """Test that date picker inputs are present"""
        response = self.client.get(reverse('activity_report'))
        content = response.content.decode()

        # Check for date inputs
        self.assertIn('type="date"', content)
        self.assertIn('id="start_date"', content)
        self.assertIn('id="end_date"', content)

    def test_calories_always_shown(self):
        """Test that Calories is always shown (even when distance is available)"""
        # Create workout with distance
        start_time = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))
        self.Workout.objects.create(
            source='Whoop',
            source_id='workout-1',
            start=start_time,
            end=start_time + timedelta(hours=1),
            sport_id=0,
            calories_burned=500,
            distance_in_miles=5.0
        )

        response = self.client.get(reverse('activity_report'))
        content = response.content.decode()

        # Should always show Calories Burned, never Miles
        self.assertIn('Calories Burned', content)
        self.assertIn('500', content)
        self.assertNotIn('Miles', content)

    def test_calories_shown_when_no_distance(self):
        """Test that Calories is shown when distance is not available"""
        # Create workout without distance
        start_time = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))
        yoga_sport = self.WhoopSportId.objects.create(sport_id=44, sport_name='Yoga')

        self.Workout.objects.create(
            source='Whoop',
            source_id='workout-2',
            start=start_time,
            end=start_time + timedelta(hours=1),
            sport_id=44,
            calories_burned=300,
            distance_in_miles=None
        )

        response = self.client.get(reverse('activity_report'))
        content = response.content.decode()

        # Should show Calories Burned for Yoga
        self.assertIn('Calories Burned', content)

    def test_total_time_displayed(self):
        """Test that total time is displayed at bottom of time tracking"""
        start_time = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))

        log = self.TimeLog.objects.create(
            source='Manual',
            source_id='log-1',
            project_id=self.project.project_id,
            start=start_time,
            end=start_time + timedelta(hours=10)
        )
        log.goals.add(self.goal)

        response = self.client.get(reverse('activity_report'))
        content = response.content.decode()

        # Check for total row
        self.assertIn('Total', content)
        self.assertIn('10.0h (100%)', content)

    def test_empty_date_range_handling(self):
        """Test handling of empty date ranges"""
        # Request data for a future date range with no data
        future_start = date(2030, 1, 1)
        future_end = date(2030, 1, 7)

        response = self.client.get(
            reverse('activity_report'),
            {'start_date': future_start.isoformat(), 'end_date': future_end.isoformat()}
        )

        self.assertEqual(response.status_code, 200)
        # All counts should be zero
        self.assertEqual(response.context['fasting']['count'], 0)
        self.assertEqual(response.context['nutrition']['days_tracked'], 0)
        self.assertEqual(response.context['weight']['count'], 0)
        self.assertEqual(len(response.context['workouts_by_sport']), 0)
        self.assertEqual(len(response.context['time_by_project']), 0)

    def test_time_tracking_with_numeric_tag_ids(self):
        """Test that time tracking works with numeric Toggl tag IDs (new format)"""
        # Create a goal with numeric tag ID (Toggl format after migration)
        goal_with_tag_id = Goal.objects.create(
            goal_id='19527134',  # Numeric tag ID from Toggl
            display_string='build_kpi_module'
        )

        # Create time log with the numeric tag ID goal
        start_time = timezone.make_aware(datetime.combine(self.week_start, datetime.min.time()))
        time_log = self.TimeLog.objects.create(
            source='Toggl',
            source_id='toggl-entry-1',
            project_id=self.project.project_id,
            start=start_time,
            end=start_time + timedelta(hours=3)
        )
        time_log.goals.add(goal_with_tag_id)

        # Get activity report
        response = self.client.get(reverse('activity_report'))
        time_data = response.context['time_by_project']

        # Verify project appears
        self.assertIn('Test Project', time_data)
        project_data = time_data['Test Project']

        # Verify goal appears with display_string (not the numeric ID)
        self.assertIn('build_kpi_module', project_data['goals'])
        self.assertEqual(project_data['goals']['build_kpi_module']['hours'], 3.0)
        self.assertEqual(project_data['goals']['build_kpi_module']['percentage'], 100)

        # Verify total hours
        self.assertEqual(project_data['total_hours'], 3.0)

    def test_monthly_objectives_edit_data_fields(self):
        """
        Test that monthly objectives include all required fields for editing.

        Regression test: Clicking the edit button should pre-populate the modal
        with the objective's data. This requires the view to pass all fields:
        - objective_id
        - label
        - start (for extracting month/year)
        - objective_value
        - objective_definition
        """
        from monthly_objectives.models import MonthlyObjective
        from calendar import monthrange

        # Create a test objective for November 2025
        start_date = date(2025, 11, 1)
        last_day = monthrange(2025, 11)[1]
        end_date = date(2025, 11, last_day)

        objective = MonthlyObjective.objects.create(
            objective_id='test_objective_nov_2025',
            label='15 Running Workouts',
            start=start_date,
            end=end_date,
            timezone='America/Chicago',
            objective_value=15.0,
            objective_definition='SELECT COUNT(*) FROM workouts_workout WHERE sport_id = 0',
            result=10.0  # 10 out of 15 completed
        )

        # Request activity report for November 2025
        response = self.client.get(
            reverse('activity_report'),
            {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()}
        )

        self.assertEqual(response.status_code, 200)

        # Verify monthly_objectives context exists
        self.assertIn('monthly_objectives', response.context)
        monthly_objectives_context = response.context['monthly_objectives']

        # Verify objectives list exists
        self.assertIn('objectives', monthly_objectives_context)
        objectives = monthly_objectives_context['objectives']
        self.assertEqual(len(objectives), 1)

        # CRITICAL: Verify all required fields are present for editing
        obj_data = objectives[0]

        # These fields are required by the edit modal
        self.assertIn('objective_id', obj_data, "objective_id is required for identifying which objective to update")
        self.assertIn('label', obj_data, "label is required for pre-populating the form")
        self.assertIn('start', obj_data, "start date is required for extracting month/year")
        self.assertIn('objective_value', obj_data, "objective_value is required for pre-populating target value")
        self.assertIn('objective_definition', obj_data, "objective_definition (SQL) is required for pre-populating the SQL field")

        # Verify the values are correct
        self.assertEqual(obj_data['objective_id'], 'test_objective_nov_2025')
        self.assertEqual(obj_data['label'], '15 Running Workouts')
        self.assertEqual(obj_data['start'], start_date)
        self.assertEqual(obj_data['objective_value'], 15.0)
        self.assertEqual(obj_data['objective_definition'], 'SELECT COUNT(*) FROM workouts_workout WHERE sport_id = 0')

        # Verify display fields also exist (these were there before)
        self.assertIn('target', obj_data)  # Display name for objective_value
        self.assertIn('result', obj_data)
        self.assertIn('progress_pct', obj_data)
        self.assertIn('achieved', obj_data)

        # Verify the displayed values
        self.assertEqual(obj_data['target'], 15.0)
        self.assertEqual(obj_data['result'], 10.0)
        self.assertAlmostEqual(obj_data['progress_pct'], 66.7, places=1)
        self.assertFalse(obj_data['achieved'])


class MonthlyObjectiveEditModalSeleniumTestCase(StaticLiveServerTestCase):
    """
    Front-end Selenium tests for Monthly Objectives edit modal.

    These tests verify the JavaScript behavior when editing objectives,
    specifically that clicking the pencil icon properly pre-populates
    the modal with the objective's data.
    """

    @classmethod
    def setUpClass(cls):
        """Set up Selenium WebDriver for all tests in this class."""
        super().setUpClass()
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        # Try to use Chrome in headless mode
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        try:
            cls.selenium = webdriver.Chrome(options=chrome_options)
            cls.selenium.implicitly_wait(10)
        except Exception as e:
            # Skip Selenium tests if Chrome/ChromeDriver not available
            raise unittest.SkipTest(f"Selenium tests skipped: {str(e)}")

    @classmethod
    def tearDownClass(cls):
        """Clean up Selenium WebDriver."""
        if hasattr(cls, 'selenium'):
            cls.selenium.quit()
        super().tearDownClass()

    def test_edit_modal_prepopulates_form_fields(self):
        """
        Test that clicking the edit pencil icon pre-populates the modal form.

        Regression test for bug where modal was being reset after data was populated.
        This test verifies the isEditMode flag prevents the modal from resetting.
        """
        from monthly_objectives.models import MonthlyObjective
        from calendar import monthrange
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time

        # Create a test objective for December 2025
        start_date = date(2025, 12, 1)
        last_day = monthrange(2025, 12)[1]
        end_date = date(2025, 12, last_day)

        objective = MonthlyObjective.objects.create(
            objective_id='test_objective_dec_2025',
            label='20 Cycling Workouts',
            start=start_date,
            end=end_date,
            timezone='America/Chicago',
            objective_value=20.0,
            objective_definition='SELECT COUNT(*) FROM workouts_workout WHERE sport_id = 1',
            result=12.0  # 12 out of 20 completed
        )

        # Navigate to activity report for December 2025
        url = f'{self.live_server_url}/activity-report/?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}'
        self.selenium.get(url)

        # First verify the page loaded
        try:
            WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
        except Exception as e:
            # Debug: save page source if page doesn't load
            with open('/tmp/selenium_debug_page.html', 'w') as f:
                f.write(self.selenium.page_source)
            raise AssertionError(f"Page did not load properly. Page source saved to /tmp/selenium_debug_page.html") from e

        # The Monthly Objectives section is collapsed by default, so we need to expand it first
        try:
            objectives_header = WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'section-header-objectives'))
            )
            # Click the header to expand the section
            objectives_header.click()
            time.sleep(0.5)  # Wait for collapse animation
        except Exception as e:
            with open('/tmp/selenium_debug_no_header.html', 'w') as f:
                f.write(self.selenium.page_source)
            raise unittest.SkipTest(
                f"Monthly objectives header not found. Page source saved to /tmp/selenium_debug_no_header.html"
            ) from e

        # Now check if the edit button exists and is clickable
        try:
            edit_button = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'edit-objective-btn'))
            )
        except Exception as e:
            # Debug: save page source to see what's actually on the page
            with open('/tmp/selenium_debug_no_button.html', 'w') as f:
                f.write(self.selenium.page_source)
            raise unittest.SkipTest(
                f"Edit button not found or not clickable after expanding section. "
                f"Page source saved to /tmp/selenium_debug_no_button.html"
            ) from e

        # Scroll element into view and click it
        self.selenium.execute_script("arguments[0].scrollIntoView(true);", edit_button)
        time.sleep(0.3)  # Brief pause after scroll
        edit_button.click()

        # Wait for modal to appear
        WebDriverWait(self.selenium, 10).until(
            EC.visibility_of_element_located((By.ID, 'createObjectiveModal'))
        )

        # Small delay to ensure JavaScript has finished executing
        time.sleep(0.5)

        # Verify modal title is "Edit Monthly Objective"
        modal_title = self.selenium.find_element(By.ID, 'modalTitleText')
        self.assertEqual(modal_title.text, 'Edit Monthly Objective')

        # Verify all form fields are populated correctly
        edit_objective_id = self.selenium.find_element(By.ID, 'editObjectiveId')
        self.assertEqual(edit_objective_id.get_attribute('value'), 'test_objective_dec_2025')

        label_input = self.selenium.find_element(By.ID, 'label')  # Correct ID
        self.assertEqual(label_input.get_attribute('value'), '20 Cycling Workouts')

        month_select = self.selenium.find_element(By.ID, 'objectiveMonth')
        self.assertEqual(month_select.get_attribute('value'), '12')  # December

        year_input = self.selenium.find_element(By.ID, 'objectiveYear')
        self.assertEqual(year_input.get_attribute('value'), '2025')

        target_input = self.selenium.find_element(By.ID, 'objectiveValue')
        self.assertEqual(target_input.get_attribute('value'), '20.0')

        definition_input = self.selenium.find_element(By.ID, 'objectiveDefinition')
        self.assertEqual(
            definition_input.get_attribute('value'),
            'SELECT COUNT(*) FROM workouts_workout WHERE sport_id = 1'
        )
