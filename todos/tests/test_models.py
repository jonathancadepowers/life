"""Tests for todos app models."""
from datetime import date
from django.test import TestCase
from django.utils import timezone

from todos.models import (
    Task, TaskState, TaskTag, TaskSchedule, TimeBlock,
    TaskDetailTemplate, TaskView,
)


class TaskStateModelTests(TestCase):
    """Tests for TaskState model."""

    def test_create_state(self):
        state = TaskState.objects.create(name='Backlog', order=0)
        self.assertEqual(str(state), 'Backlog')
        self.assertEqual(state.order, 0)
        self.assertFalse(state.is_system)
        self.assertFalse(state.is_terminal)

    def test_ordering(self):
        # Note: "Inbox" at order=0 is created by migration 0008
        s1 = TaskState.objects.create(name='B State', order=2)
        s2 = TaskState.objects.create(name='A State', order=1)
        states = list(TaskState.objects.all())
        # Inbox(0), A State(1), B State(2)
        self.assertEqual(states[1], s2)
        self.assertEqual(states[2], s1)

    def test_unique_name(self):
        TaskState.objects.create(name='Done')
        with self.assertRaises(Exception):
            TaskState.objects.create(name='Done')

    def test_single_terminal_state_enforcement(self):
        """Setting a state as terminal should unset other terminal states."""
        s1 = TaskState.objects.create(name='Done', is_terminal=True)
        s2 = TaskState.objects.create(name='Complete', is_terminal=True)
        s1.refresh_from_db()
        self.assertFalse(s1.is_terminal)
        self.assertTrue(s2.is_terminal)

    def test_non_terminal_save_does_not_affect_others(self):
        s1 = TaskState.objects.create(name='Done', is_terminal=True)
        s2 = TaskState.objects.create(name='In Progress', is_terminal=False)
        s1.refresh_from_db()
        self.assertTrue(s1.is_terminal)
        self.assertFalse(s2.is_terminal)


class TaskTagModelTests(TestCase):
    """Tests for TaskTag model."""

    def test_create_tag(self):
        tag = TaskTag.objects.create(name='urgent')
        self.assertEqual(str(tag), 'urgent')

    def test_unique_name(self):
        TaskTag.objects.create(name='bug')
        with self.assertRaises(Exception):
            TaskTag.objects.create(name='bug')

    def test_ordering_alphabetical(self):
        TaskTag.objects.create(name='zebra')
        TaskTag.objects.create(name='alpha')
        tags = list(TaskTag.objects.all())
        self.assertEqual(tags[0].name, 'alpha')
        self.assertEqual(tags[1].name, 'zebra')


class TaskModelTests(TestCase):
    """Tests for Task model."""

    def test_create_task(self):
        task = Task.objects.create(title='My Task')
        self.assertEqual(str(task), 'My Task')
        self.assertEqual(task.details, '')
        self.assertFalse(task.critical)
        self.assertIsNone(task.state)
        self.assertIsNone(task.deadline)
        self.assertFalse(task.deadline_dismissed)
        self.assertIsNone(task.done_for_day)

    def test_task_with_state(self):
        state = TaskState.objects.create(name='Backlog')
        task = Task.objects.create(title='Task', state=state)
        self.assertEqual(task.state, state)

    def test_state_set_null_on_delete(self):
        state = TaskState.objects.create(name='Temp')
        task = Task.objects.create(title='Task', state=state)
        state.delete()
        task.refresh_from_db()
        self.assertIsNone(task.state)

    def test_task_tags(self):
        task = Task.objects.create(title='Task')
        t1 = TaskTag.objects.create(name='tag1')
        t2 = TaskTag.objects.create(name='tag2')
        task.tags.add(t1, t2)
        self.assertEqual(task.tags.count(), 2)

    def test_task_with_deadline(self):
        task = Task.objects.create(title='Task', deadline=date(2026, 3, 1))
        self.assertEqual(task.deadline, date(2026, 3, 1))

    def test_task_done_for_day(self):
        today = date.today()
        task = Task.objects.create(title='Task', done_for_day=today)
        self.assertEqual(task.done_for_day, today)


class TaskScheduleModelTests(TestCase):
    """Tests for TaskSchedule model."""

    def test_create_schedule(self):
        task = Task.objects.create(title='Task')
        now = timezone.now()
        schedule = TaskSchedule.objects.create(
            task=task,
            start_time=now,
            end_time=now + timezone.timedelta(hours=1)
        )
        self.assertIn(task.title, str(schedule))

    def test_cascade_delete(self):
        task = Task.objects.create(title='Task')
        TaskSchedule.objects.create(
            task=task,
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1)
        )
        task.delete()
        self.assertEqual(TaskSchedule.objects.count(), 0)

    def test_ordering_by_start_time(self):
        task = Task.objects.create(title='Task')
        now = timezone.now()
        s2 = TaskSchedule.objects.create(task=task, start_time=now + timezone.timedelta(hours=2), end_time=now + timezone.timedelta(hours=3))
        s1 = TaskSchedule.objects.create(task=task, start_time=now, end_time=now + timezone.timedelta(hours=1))
        schedules = list(TaskSchedule.objects.all())
        self.assertEqual(schedules[0], s1)
        self.assertEqual(schedules[1], s2)


class TimeBlockModelTests(TestCase):
    """Tests for TimeBlock model."""

    def test_create_time_block(self):
        now = timezone.now()
        block = TimeBlock.objects.create(
            name='Focus Time',
            start_time=now,
            end_time=now + timezone.timedelta(hours=2)
        )
        self.assertEqual(str(block), 'Focus Time')


class TaskDetailTemplateModelTests(TestCase):
    """Tests for TaskDetailTemplate model."""

    def test_create_template(self):
        t = TaskDetailTemplate.objects.create(name='Standup', content='## Notes\n- ')
        self.assertEqual(str(t), 'Standup')
        self.assertFalse(t.is_default)

    def test_single_default_enforcement(self):
        t1 = TaskDetailTemplate.objects.create(name='T1', content='a', is_default=True)
        t2 = TaskDetailTemplate.objects.create(name='T2', content='b', is_default=True)
        t1.refresh_from_db()
        self.assertFalse(t1.is_default)
        self.assertTrue(t2.is_default)

    def test_non_default_does_not_affect_others(self):
        t1 = TaskDetailTemplate.objects.create(name='T1', content='a', is_default=True)
        TaskDetailTemplate.objects.create(name='T2', content='b', is_default=False)
        t1.refresh_from_db()
        self.assertTrue(t1.is_default)


class TaskViewModelTests(TestCase):
    """Tests for TaskView model."""

    def test_create_view(self):
        v = TaskView.objects.create(name='My View', settings={'filter': 'all'})
        self.assertEqual(str(v), 'My View')
        self.assertEqual(v.settings, {'filter': 'all'})

    def test_single_default_enforcement(self):
        v1 = TaskView.objects.create(name='V1', is_default=True)
        v2 = TaskView.objects.create(name='V2', is_default=True)
        v1.refresh_from_db()
        self.assertFalse(v1.is_default)
        self.assertTrue(v2.is_default)

    def test_default_dict_settings(self):
        v = TaskView.objects.create(name='V')
        self.assertEqual(v.settings, {})
