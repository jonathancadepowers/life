from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock
import json

from targets.models import Target, DailyAgenda
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

        # Create test target
        self.target = Target.objects.create(
            target_id='test_target_1',
            target_name='Test Target 1',
            goal_id=self.goal
        )

        # Create test agenda for today
        self.today = timezone.now().date()
        self.agenda = DailyAgenda.objects.create(
            date=self.today,
            project_1=self.project,
            goal_1=self.goal,
            target_1=self.target,
            target_1_score=1.0,
            notes='# Test Notes\n- Item 1'
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
            'notes': '# Tomorrow Notes'
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
        self.assertEqual(agenda.target_1.target_name, 'New target for tomorrow')
        self.assertEqual(agenda.notes, '# Tomorrow Notes')

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
            'notes': '# Updated Notes'
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
        self.assertEqual(agenda.target_1.target_name, 'Updated target')
        self.assertEqual(agenda.notes, '# Updated Notes')

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

    def test_get_targets_for_goal(self):
        """Test getting targets for a goal"""
        response = self.client.get(
            reverse('get_targets_for_goal'),
            {'goal_id': self.goal.goal_id}
        )

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertIn('targets', result)
        self.assertEqual(len(result['targets']), 1)
        self.assertEqual(result['targets'][0]['target_id'], self.target.target_id)

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
        # Create a second target
        target2 = Target.objects.create(
            target_id='test_target_2',
            target_name='Test Target 2',
            goal_id=self.goal
        )
        self.agenda.target_2 = target2
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
        # Create additional targets
        target2 = Target.objects.create(
            target_id='test_target_2',
            target_name='Test Target 2',
            goal_id=self.goal
        )
        target3 = Target.objects.create(
            target_id='test_target_3',
            target_name='Test Target 3',
            goal_id=self.goal
        )
        self.agenda.target_2 = target2
        self.agenda.target_3 = target3
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
        # Create a second target
        target2 = Target.objects.create(
            target_id='test_target_2',
            target_name='Test Target 2',
            goal_id=self.goal
        )
        self.agenda.target_2 = target2
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
        self.assertEqual(result['agenda']['notes'], '# Test Notes\n- Item 1')

    @patch('time_logs.services.toggl_client.TogglAPIClient')
    def test_get_toggl_time_today(self, mock_toggl_client):
        """Test getting Toggl time for today"""
        # Mock Toggl API response
        mock_client_instance = MagicMock()
        mock_client_instance.get_time_entries.return_value = [
            {
                'id': 1,
                'project_id': int(self.project.project_id),
                'tags': [self.goal.goal_id],
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
                'tags': [self.goal.goal_id],
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


class DailyAgendaModelTestCase(TestCase):
    """Tests for Daily Agenda model"""

    def test_create_daily_agenda(self):
        """Test creating a daily agenda"""
        today = timezone.now().date()
        agenda = DailyAgenda.objects.create(
            date=today,
            notes='Test notes'
        )

        self.assertEqual(agenda.date, today)
        self.assertEqual(agenda.notes, 'Test notes')
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


class TargetModelTestCase(TestCase):
    """Tests for Target model"""

    def test_create_target(self):
        """Test creating a target"""
        goal = Goal.objects.create(
            goal_id='test_goal',
            display_string='Test Goal'
        )

        target = Target.objects.create(
            target_id='test_target',
            target_name='Test Target',
            goal_id=goal
        )

        self.assertEqual(target.target_id, 'test_target')
        self.assertEqual(target.target_name, 'Test Target')
        self.assertEqual(target.goal_id, goal)
        self.assertEqual(str(target), 'Test Target')
