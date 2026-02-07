"""
Management command to populate the database with fake but realistic data for testing.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
import random

from workouts.models import Workout
from weight.models import WeighIn
from fasting.models import FastingSession
from nutrition.models import NutritionEntry
from time_logs.models import TimeLog
from projects.models import Project
from goals.models import Goal
from targets.models import Target, DailyAgenda


class Command(BaseCommand):
    help = 'Populate database with fake but realistic data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=60,
            help='Number of days of historical data to generate (default: 60)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing test data before generating new data'
        )

    def handle(self, *_args, **options):
        days = options['days']
        clear = options['clear']

        if clear:
            self.stdout.write('Clearing existing test data...')
            # Only delete 'Manual' or 'Test' source data
            Workout.objects.filter(source='Test').delete()
            WeighIn.objects.filter(source='Test').delete()
            FastingSession.objects.filter(source='Test').delete()
            NutritionEntry.objects.filter(source='Test').delete()
            TimeLog.objects.filter(source='Test').delete()
            DailyAgenda.objects.filter(notes__contains='[TEST]').delete()
            self.stdout.write(self.style.SUCCESS('✓ Cleared test data'))

        self.stdout.write(f'\nGenerating {days} days of fake data...\n')

        # Get or create test projects and goals
        projects, goals = self._create_projects_and_goals()

        # Generate data for each day
        today = date.today()
        start_date = today - timedelta(days=days)

        created_counts = {
            'workouts': 0,
            'weight': 0,
            'fasting': 0,
            'nutrition': 0,
            'time_logs': 0,
            'agendas': 0
        }

        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)

            # Skip some days randomly to make it realistic
            if random.random() < 0.15:  # 15% chance to skip a day
                continue

            # Generate workouts (60% of days have workouts)
            if random.random() < 0.6:
                created_counts['workouts'] += self._create_workouts(current_date)

            # Generate weight entries (80% of days)
            if random.random() < 0.8:
                created_counts['weight'] += self._create_weight_entry(current_date)

            # Generate fasting sessions (70% of days)
            if random.random() < 0.7:
                created_counts['fasting'] += self._create_fasting_session(current_date)

            # Generate nutrition entries (85% of days)
            if random.random() < 0.85:
                created_counts['nutrition'] += self._create_nutrition_entries(current_date)

            # Generate time logs (weekdays mostly - 90% on weekdays, 20% on weekends)
            is_weekday = current_date.weekday() < 5
            if (is_weekday and random.random() < 0.9) or (not is_weekday and random.random() < 0.2):
                created_counts['time_logs'] += self._create_time_logs(current_date, projects, goals)

            # Generate daily agendas (70% of days)
            if random.random() < 0.7:
                created_counts['agendas'] += self._create_daily_agenda(current_date, projects, goals)

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('✓ Data generation complete!'))
        self.stdout.write('='*60)
        self.stdout.write(f"Workouts created:        {created_counts['workouts']}")
        self.stdout.write(f"Weight entries:          {created_counts['weight']}")
        self.stdout.write(f"Fasting sessions:        {created_counts['fasting']}")
        self.stdout.write(f"Nutrition entries:       {created_counts['nutrition']}")
        self.stdout.write(f"Time logs:               {created_counts['time_logs']}")
        self.stdout.write(f"Daily agendas:           {created_counts['agendas']}")
        self.stdout.write('='*60 + '\n')

    def _create_projects_and_goals(self):
        """Create or get test projects and goals"""
        projects = []
        goals = []

        # Projects
        project_data = [
            (999001, 'Personal Development'),
            (999002, 'Health & Fitness'),
            (999003, 'Side Projects'),
        ]

        for project_id, name in project_data:
            project, _ = Project.objects.get_or_create(
                project_id=project_id,
                defaults={'display_string': name}
            )
            projects.append(project)

        # Goals
        goal_data = [
            ('test_goal_fitness', 'Daily Exercise'),
            ('test_goal_learning', 'Learn New Skills'),
            ('test_goal_coding', 'Build Apps'),
            ('test_goal_reading', 'Reading'),
        ]

        for goal_id, name in goal_data:
            goal, _ = Goal.objects.get_or_create(
                goal_id=goal_id,
                defaults={'display_string': name}
            )
            goals.append(goal)

        return projects, goals

    def _create_workouts(self, current_date):
        """Create 1-2 workouts for the day"""
        count = 0
        sport_choices = [
            (0, 'Running'),
            (48, 'Cycling'),
            (63, 'Functional Fitness'),
            (45, 'Weightlifting'),
            (44, 'Yoga'),
            (49, 'Walking'),
        ]

        num_workouts = random.choices([1, 2], weights=[0.8, 0.2])[0]

        for i in range(num_workouts):
            sport_id, sport_name = random.choice(sport_choices)

            # Random start time
            hour = random.randint(6, 18)
            minute = random.randint(0, 59)
            start = timezone.make_aware(datetime.combine(current_date, datetime.min.time().replace(hour=hour, minute=minute)))

            # Duration: 20-90 minutes
            duration_minutes = random.randint(20, 90)
            end = start + timedelta(minutes=duration_minutes)

            # Calories and heart rate based on sport and duration
            calories = Decimal(str(random.randint(150, 600)))
            avg_hr = random.randint(120, 165)
            max_hr = avg_hr + random.randint(10, 30)

            Workout.objects.update_or_create(
                source='Test',
                source_id=f'test-workout-{current_date}-{i}',
                defaults={
                    'start': start,
                    'end': end,
                    'sport_id': sport_id,
                    'average_heart_rate': avg_hr,
                    'max_heart_rate': max_hr,
                    'calories_burned': calories
                }
            )
            count += 1

        return count

    def _create_weight_entry(self, current_date):
        """Create a weight entry with gradual variation"""
        # Base weight with small random variation
        base_weight = 180.0
        variation = random.uniform(-2.0, 2.0)
        weight = Decimal(str(round(base_weight + variation, 1)))

        hour = random.randint(6, 9)
        measurement_time = timezone.make_aware(
            datetime.combine(current_date, datetime.min.time().replace(hour=hour))
        )

        WeighIn.objects.update_or_create(
            source='Test',
            source_id=f'test-weight-{current_date}',
            defaults={
                'measurement_time': measurement_time,
                'weight': weight
            }
        )
        return 1

    def _create_fasting_session(self, current_date):
        """Create a fasting session"""
        # Typical intermittent fasting: 14-18 hours
        duration = Decimal(str(random.randint(14, 18)))

        # End time: usually morning
        end_hour = random.randint(10, 12)
        fast_end = timezone.make_aware(
            datetime.combine(current_date, datetime.min.time().replace(hour=end_hour))
        )

        FastingSession.objects.update_or_create(
            source='Test',
            source_id=f'test-fast-{current_date}',
            defaults={
                'fast_end_date': fast_end,
                'duration': duration
            }
        )
        return 1

    def _create_nutrition_entries(self, current_date):
        """Create 2-4 nutrition entries (meals) for the day"""
        count = 0
        num_meals = random.randint(2, 4)

        meal_templates = [
            {'name': 'Breakfast', 'calories': (300, 500), 'protein': (15, 30), 'carbs': (30, 60), 'fat': (10, 25)},
            {'name': 'Lunch', 'calories': (500, 800), 'protein': (30, 50), 'carbs': (50, 80), 'fat': (15, 35)},
            {'name': 'Dinner', 'calories': (500, 800), 'protein': (30, 50), 'carbs': (40, 70), 'fat': (15, 35)},
            {'name': 'Snack', 'calories': (150, 300), 'protein': (5, 15), 'carbs': (15, 40), 'fat': (5, 15)},
        ]

        selected_meals = random.sample(meal_templates, num_meals)

        for i, meal in enumerate(selected_meals):
            hour = 8 + (i * 4)  # Spread meals throughout the day
            consumption_time = timezone.make_aware(
                datetime.combine(current_date, datetime.min.time().replace(hour=hour))
            )

            NutritionEntry.objects.update_or_create(
                source='Test',
                source_id=f'test-nutrition-{current_date}-{i}',
                defaults={
                    'consumption_date': consumption_time,
                    'calories': Decimal(str(random.randint(*meal['calories']))),
                    'protein': Decimal(str(random.randint(*meal['protein']))),
                    'carbs': Decimal(str(random.randint(*meal['carbs']))),
                    'fat': Decimal(str(random.randint(*meal['fat'])))
                }
            )
            count += 1

        return count

    def _create_time_logs(self, current_date, projects, goals):
        """Create 2-5 time log entries for the day"""
        count = 0
        num_entries = random.randint(2, 5)

        current_time = timezone.make_aware(
            datetime.combine(current_date, datetime.min.time().replace(hour=9))
        )

        for i in range(num_entries):
            project = random.choice(projects)
            project_goals = random.sample(goals, k=random.randint(1, 2))

            # Duration: 30 minutes to 3 hours
            duration_minutes = random.randint(30, 180)
            start = current_time
            end = start + timedelta(minutes=duration_minutes)

            time_log, created = TimeLog.objects.update_or_create(
                source='Test',
                source_id=f'test-timelog-{current_date}-{i}',
                defaults={
                    'project_id': project.project_id,
                    'start': start,
                    'end': end
                }
            )
            time_log.goals.set(project_goals)

            # Move current time forward with a small break
            current_time = end + timedelta(minutes=random.randint(15, 45))
            count += 1

        return count

    def _set_agenda_target(self, agenda, slot, project, goal):
        """Set a single target slot (1, 2, or 3) on an agenda with a random score."""
        setattr(agenda, f'project_{slot}', project)
        setattr(agenda, f'goal_{slot}', goal)

        if not goal:
            return

        target, _ = Target.objects.get_or_create(
            target_id=f'test-target-{goal.goal_id}-{slot}',
            defaults={
                'target_name': f'Work on {goal.display_string}',
                'goal_id': goal
            }
        )
        setattr(agenda, f'target_{slot}', target)

        if random.random() < 0.7:
            setattr(agenda, f'target_{slot}_score', random.choice([0.0, 0.5, 1.0]))

    def _create_daily_agenda(self, current_date, projects, goals):
        """Create a daily agenda entry"""
        if DailyAgenda.objects.filter(date=current_date).exclude(notes__contains='[TEST]').exists():
            return 0

        num_targets = random.randint(1, 3)
        selected_projects = random.sample(projects, k=min(num_targets, len(projects)))
        selected_goals = random.sample(goals, k=min(num_targets, len(goals)))

        agenda, created = DailyAgenda.objects.get_or_create(
            date=current_date,
            defaults={'other_plans': f'[TEST] Daily agenda for {current_date}'}
        )
        if not created:
            agenda.other_plans = f'[TEST] Daily agenda for {current_date}'

        for i in range(num_targets):
            slot = i + 1
            project = selected_projects[i] if i < len(selected_projects) else None
            goal = selected_goals[i] if i < len(selected_goals) else None
            self._set_agenda_target(agenda, slot, project, goal)

        scores = [getattr(agenda, f'target_{s}_score') for s in range(1, 4)
                   if getattr(agenda, f'target_{s}_score') is not None]
        if scores:
            agenda.day_score = sum(scores) / len(scores)

        agenda.save()
        return 1
