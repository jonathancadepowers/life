from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock
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
        self.assertEqual(agenda.target_1, 'New target for tomorrow')  # Now just text
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
        self.assertEqual(agenda.target_1, 'Updated target')  # Now just text
        self.assertEqual(agenda.notes, '# Updated Notes')

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
            'notes': '# Test Notes\n- Added at 10pm local time\n- Should save to Oct 28'
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
        self.assertEqual(agenda.notes, '# Test Notes\n- Added at 10pm local time\n- Should save to Oct 28')

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
