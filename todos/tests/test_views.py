"""Tests for todos app views."""
import json
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from todos.models import (
    Task, TaskState, TaskTag, TaskSchedule, TimeBlock,
    TaskDetailTemplate, TaskView,
)
from calendar_events.models import CalendarEvent


class TodosViewTestBase(TestCase):
    """Base class with common setup for todos view tests.

    Note: Migration 0008 creates an 'Inbox' state at order=0,
    so it always exists in the test database.
    """

    def setUp(self):
        self.client = Client()
        self.inbox_state = TaskState.objects.get(name='Inbox')
        self.state1 = TaskState.objects.create(name='Backlog', order=1)
        self.state2 = TaskState.objects.create(name='In Progress', order=2)

    def post_json(self, url, data=None):
        return self.client.post(
            url,
            data=json.dumps(data or {}),
            content_type='application/json'
        )

    def patch_json(self, url, data=None):
        return self.client.patch(
            url,
            data=json.dumps(data or {}),
            content_type='application/json'
        )

    def delete_json(self, url):
        return self.client.delete(url, content_type='application/json')


class TaskListPageTests(TodosViewTestBase):
    """Tests for the main task list page."""

    def test_page_loads(self):
        resp = self.client.get(reverse('todos:task_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('tasks', resp.context)
        self.assertIn('states', resp.context)
        self.assertIn('tags', resp.context)

    def test_page_includes_calendar_events_json(self):
        resp = self.client.get(reverse('todos:task_list'))
        self.assertIn('calendar_events', resp.context)
        self.assertIn('time_blocks', resp.context)
        self.assertIn('detail_templates', resp.context)
        self.assertIn('saved_views', resp.context)


class TaskCRUDTests(TodosViewTestBase):
    """Tests for task create/read/update/delete."""

    def test_create_task(self):
        resp = self.post_json(reverse('todos:create_task'), {'title': 'New Task'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['task']['title'], 'New Task')
        self.assertEqual(Task.objects.count(), 1)

    def test_create_task_assigns_first_state(self):
        resp = self.post_json(reverse('todos:create_task'), {'title': 'Task'})
        data = resp.json()
        # First state by ordering is Inbox (order=0, from migration 0008)
        self.assertEqual(data['task']['state_id'], self.inbox_state.id)

    def test_create_task_empty_title(self):
        resp = self.post_json(reverse('todos:create_task'), {'title': ''})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])

    def test_create_task_missing_title(self):
        resp = self.post_json(reverse('todos:create_task'), {})
        self.assertEqual(resp.status_code, 400)

    def test_create_task_invalid_json(self):
        resp = self.client.post(
            reverse('todos:create_task'),
            data='not json',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_task(self):
        task = Task.objects.create(title='Test', state=self.state1)
        resp = self.client.get(reverse('todos:get_task', args=[task.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['task']['title'], 'Test')

    def test_get_task_not_found(self):
        resp = self.client.get(reverse('todos:get_task', args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_update_task_title(self):
        task = Task.objects.create(title='Old', state=self.state1)
        resp = self.patch_json(
            reverse('todos:update_task', args=[task.id]),
            {'title': 'New'}
        )
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.title, 'New')

    def test_update_task_details(self):
        task = Task.objects.create(title='Task', state=self.state1)
        resp = self.patch_json(
            reverse('todos:update_task', args=[task.id]),
            {'details': 'Some details'}
        )
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.details, 'Some details')

    def test_update_task_critical(self):
        task = Task.objects.create(title='Task', state=self.state1)
        self.patch_json(
            reverse('todos:update_task', args=[task.id]),
            {'critical': True}
        )
        task.refresh_from_db()
        self.assertTrue(task.critical)

    def test_update_task_state_sets_state_changed_at(self):
        task = Task.objects.create(title='Task', state=self.state1)
        self.assertIsNone(task.state_changed_at)
        self.patch_json(
            reverse('todos:update_task', args=[task.id]),
            {'state_id': self.state2.id}
        )
        task.refresh_from_db()
        self.assertEqual(task.state, self.state2)
        self.assertIsNotNone(task.state_changed_at)

    def test_update_task_same_state_no_timestamp_change(self):
        fixed_time = timezone.now() - timedelta(days=1)
        task = Task.objects.create(title='Task', state=self.state1, state_changed_at=fixed_time)
        self.patch_json(
            reverse('todos:update_task', args=[task.id]),
            {'state_id': self.state1.id}
        )
        task.refresh_from_db()
        # state_changed_at should not have changed since state_id is the same
        self.assertEqual(task.state_changed_at, fixed_time)

    def test_update_task_deadline(self):
        task = Task.objects.create(title='Task', state=self.state1)
        self.patch_json(
            reverse('todos:update_task', args=[task.id]),
            {'deadline': '2026-03-15'}
        )
        task.refresh_from_db()
        from datetime import date
        self.assertEqual(task.deadline, date(2026, 3, 15))

    def test_update_task_clear_deadline(self):
        from datetime import date
        task = Task.objects.create(title='Task', state=self.state1, deadline=date(2026, 1, 1))
        self.patch_json(
            reverse('todos:update_task', args=[task.id]),
            {'deadline': None}
        )
        task.refresh_from_db()
        self.assertIsNone(task.deadline)

    def test_update_task_deadline_dismissed(self):
        task = Task.objects.create(title='Task', state=self.state1)
        self.patch_json(
            reverse('todos:update_task', args=[task.id]),
            {'deadline_dismissed': True}
        )
        task.refresh_from_db()
        self.assertTrue(task.deadline_dismissed)

    def test_update_task_not_found(self):
        resp = self.patch_json(
            reverse('todos:update_task', args=[9999]),
            {'title': 'X'}
        )
        self.assertEqual(resp.status_code, 404)

    def test_update_task_invalid_state(self):
        task = Task.objects.create(title='Task', state=self.state1)
        resp = self.patch_json(
            reverse('todos:update_task', args=[task.id]),
            {'state_id': 99999}
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_task(self):
        task = Task.objects.create(title='Task', state=self.state1)
        resp = self.delete_json(reverse('todos:delete_task', args=[task.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(Task.objects.count(), 0)

    def test_delete_task_not_found(self):
        resp = self.delete_json(reverse('todos:delete_task', args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_delete_task_wrong_method(self):
        task = Task.objects.create(title='Task')
        resp = self.client.get(reverse('todos:delete_task', args=[task.id]))
        self.assertEqual(resp.status_code, 405)


class ReorderTests(TodosViewTestBase):
    """Tests for task and state reordering."""

    def test_reorder_tasks(self):
        t1 = Task.objects.create(title='A', order=0)
        t2 = Task.objects.create(title='B', order=1)
        resp = self.post_json(
            reverse('todos:reorder_tasks'),
            {'task_ids': [t2.id, t1.id]}
        )
        self.assertEqual(resp.status_code, 200)
        t1.refresh_from_db()
        t2.refresh_from_db()
        self.assertEqual(t2.order, 0)
        self.assertEqual(t1.order, 1)

    def test_reorder_states(self):
        resp = self.post_json(
            reverse('todos:reorder_states'),
            {'order': [self.state2.id, self.state1.id]}
        )
        self.assertEqual(resp.status_code, 200)
        self.state1.refresh_from_db()
        self.state2.refresh_from_db()
        self.assertEqual(self.state2.order, 0)
        self.assertEqual(self.state1.order, 1)


class StateCRUDTests(TodosViewTestBase):
    """Tests for state create/read/update/delete."""

    def test_list_states(self):
        resp = self.client.get(reverse('todos:list_states'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['states']), 3)  # Inbox + Backlog + In Progress

    def test_list_states_includes_task_count(self):
        Task.objects.create(title='T1', state=self.state1)
        Task.objects.create(title='T2', state=self.state1)
        resp = self.client.get(reverse('todos:list_states'))
        states = resp.json()['states']
        backlog = next(s for s in states if s['name'] == 'Backlog')
        self.assertEqual(backlog['task_count'], 2)

    def test_create_state(self):
        resp = self.post_json(reverse('todos:create_state'), {'name': 'Done'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['state']['name'], 'Done')
        self.assertEqual(TaskState.objects.count(), 4)  # Inbox + Backlog + In Progress + Done

    def test_create_state_auto_order(self):
        resp = self.post_json(reverse('todos:create_state'), {'name': 'Done'})
        # Order = count before creation (3 existing: Inbox, Backlog, In Progress)
        self.assertEqual(resp.json()['state']['order'], 3)

    def test_create_state_empty_name(self):
        resp = self.post_json(reverse('todos:create_state'), {'name': ''})
        self.assertEqual(resp.status_code, 400)

    def test_create_state_duplicate_name(self):
        resp = self.post_json(reverse('todos:create_state'), {'name': 'Backlog'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already exists', resp.json()['error'])

    def test_get_state_info(self):
        Task.objects.create(title='T', state=self.state1)
        resp = self.client.get(reverse('todos:get_state_info', args=[self.state1.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['state']['task_count'], 1)
        self.assertEqual(data['total_states'], 3)  # Inbox + Backlog + In Progress

    def test_get_state_info_not_found(self):
        resp = self.client.get(reverse('todos:get_state_info', args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_update_state_name(self):
        resp = self.patch_json(
            reverse('todos:update_state', args=[self.state1.id]),
            {'name': 'Todo'}
        )
        self.assertEqual(resp.status_code, 200)
        self.state1.refresh_from_db()
        self.assertEqual(self.state1.name, 'Todo')

    def test_update_state_icon(self):
        self.patch_json(
            reverse('todos:update_state', args=[self.state1.id]),
            {'bootstrap_icon': 'bi-inbox'}
        )
        self.state1.refresh_from_db()
        self.assertEqual(self.state1.bootstrap_icon, 'bi-inbox')

    def test_update_state_terminal(self):
        self.patch_json(
            reverse('todos:update_state', args=[self.state1.id]),
            {'is_terminal': True}
        )
        self.state1.refresh_from_db()
        self.assertTrue(self.state1.is_terminal)

    def test_update_state_system_cannot_be_terminal(self):
        sys_state = TaskState.objects.create(name='System', is_system=True)
        resp = self.patch_json(
            reverse('todos:update_state', args=[sys_state.id]),
            {'is_terminal': True}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('System states', resp.json()['error'])

    def test_update_state_not_found(self):
        resp = self.patch_json(
            reverse('todos:update_state', args=[9999]),
            {'name': 'X'}
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_state(self):
        resp = self.delete_json(reverse('todos:delete_state', args=[self.state2.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TaskState.objects.count(), 2)  # Inbox + Backlog remain

    def test_delete_state_cannot_delete_system(self):
        sys_state = TaskState.objects.create(name='Sys', is_system=True)
        resp = self.delete_json(reverse('todos:delete_state', args=[sys_state.id]))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('system state', resp.json()['error'].lower())

    def test_delete_state_cannot_delete_last(self):
        self.state1.delete()
        self.state2.delete()
        # Only Inbox remains — cannot delete the last state
        resp = self.delete_json(reverse('todos:delete_state', args=[self.inbox_state.id]))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('last state', resp.json()['error'].lower())

    def test_delete_state_with_task_migration(self):
        task = Task.objects.create(title='T', state=self.state1)
        resp = self.client.post(
            reverse('todos:delete_state', args=[self.state1.id]),
            data=json.dumps({'move_to_state_id': self.state2.id}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.state, self.state2)

    def test_delete_state_not_found(self):
        resp = self.delete_json(reverse('todos:delete_state', args=[9999]))
        self.assertEqual(resp.status_code, 404)


class TagCRUDTests(TodosViewTestBase):
    """Tests for tag create/read/update/delete."""

    def test_list_tags(self):
        TaskTag.objects.create(name='bug')
        resp = self.client.get(reverse('todos:list_tags'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['tags']), 1)

    def test_create_tag(self):
        resp = self.post_json(reverse('todos:create_tag'), {'name': 'feature'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['created'])

    def test_create_tag_get_or_create(self):
        TaskTag.objects.create(name='bug')
        resp = self.post_json(reverse('todos:create_tag'), {'name': 'bug'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['created'])
        self.assertEqual(TaskTag.objects.count(), 1)

    def test_create_tag_empty_name(self):
        resp = self.post_json(reverse('todos:create_tag'), {'name': ''})
        self.assertEqual(resp.status_code, 400)

    def test_add_tag_to_task_by_id(self):
        task = Task.objects.create(title='T')
        tag = TaskTag.objects.create(name='urgent')
        resp = self.post_json(
            reverse('todos:add_tag_to_task', args=[task.id]),
            {'tag_id': tag.id}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(task.tags.count(), 1)

    def test_add_tag_to_task_by_name(self):
        task = Task.objects.create(title='T')
        resp = self.post_json(
            reverse('todos:add_tag_to_task', args=[task.id]),
            {'name': 'new-tag'}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(task.tags.count(), 1)
        self.assertTrue(TaskTag.objects.filter(name='new-tag').exists())

    def test_add_tag_to_task_missing_both(self):
        task = Task.objects.create(title='T')
        resp = self.post_json(
            reverse('todos:add_tag_to_task', args=[task.id]),
            {}
        )
        self.assertEqual(resp.status_code, 400)

    def test_add_tag_to_nonexistent_task(self):
        resp = self.post_json(
            reverse('todos:add_tag_to_task', args=[9999]),
            {'name': 'tag'}
        )
        self.assertEqual(resp.status_code, 404)

    def test_remove_tag_from_task(self):
        task = Task.objects.create(title='T')
        tag = TaskTag.objects.create(name='bug')
        task.tags.add(tag)
        resp = self.post_json(
            reverse('todos:remove_tag_from_task', args=[task.id]),
            {'tag_id': tag.id}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(task.tags.count(), 0)

    def test_remove_tag_missing_tag_id(self):
        task = Task.objects.create(title='T')
        resp = self.post_json(
            reverse('todos:remove_tag_from_task', args=[task.id]),
            {}
        )
        self.assertEqual(resp.status_code, 400)

    def test_delete_tag(self):
        tag = TaskTag.objects.create(name='old')
        resp = self.delete_json(reverse('todos:delete_tag', args=[tag.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TaskTag.objects.count(), 0)

    def test_delete_tag_not_found(self):
        resp = self.delete_json(reverse('todos:delete_tag', args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_rename_tag(self):
        tag = TaskTag.objects.create(name='old')
        resp = self.patch_json(
            reverse('todos:rename_tag', args=[tag.id]),
            {'name': 'new'}
        )
        self.assertEqual(resp.status_code, 200)
        tag.refresh_from_db()
        self.assertEqual(tag.name, 'new')

    def test_rename_tag_duplicate(self):
        TaskTag.objects.create(name='existing')
        tag = TaskTag.objects.create(name='old')
        resp = self.patch_json(
            reverse('todos:rename_tag', args=[tag.id]),
            {'name': 'existing'}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already exists', resp.json()['error'])

    def test_rename_tag_empty_name(self):
        tag = TaskTag.objects.create(name='old')
        resp = self.patch_json(
            reverse('todos:rename_tag', args=[tag.id]),
            {'name': ''}
        )
        self.assertEqual(resp.status_code, 400)

    def test_rename_tag_not_found(self):
        resp = self.patch_json(
            reverse('todos:rename_tag', args=[9999]),
            {'name': 'x'}
        )
        self.assertEqual(resp.status_code, 404)


class TimeBlockTests(TodosViewTestBase):
    """Tests for time block CRUD."""

    def test_create_time_block(self):
        resp = self.post_json(
            reverse('todos:create_time_block'),
            {
                'name': 'Focus',
                'start_time': '2026-02-07T09:00:00+00:00',
                'end_time': '2026-02-07T11:00:00+00:00'
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['time_block']['name'], 'Focus')
        self.assertEqual(TimeBlock.objects.count(), 1)

    def test_create_time_block_default_end_time(self):
        resp = self.post_json(
            reverse('todos:create_time_block'),
            {
                'name': 'Quick',
                'start_time': '2026-02-07T09:00:00+00:00'
            }
        )
        self.assertEqual(resp.status_code, 200)
        block = TimeBlock.objects.first()
        # Default 30 min after start
        diff = (block.end_time - block.start_time).total_seconds()
        self.assertEqual(diff, 30 * 60)

    def test_create_time_block_missing_name(self):
        resp = self.post_json(
            reverse('todos:create_time_block'),
            {'start_time': '2026-02-07T09:00:00+00:00'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_time_block_missing_start(self):
        resp = self.post_json(
            reverse('todos:create_time_block'),
            {'name': 'Block'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_update_time_block(self):
        block = TimeBlock.objects.create(
            name='Old',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        resp = self.patch_json(
            reverse('todos:update_time_block', args=[block.id]),
            {'name': 'Updated'}
        )
        self.assertEqual(resp.status_code, 200)
        block.refresh_from_db()
        self.assertEqual(block.name, 'Updated')

    def test_update_time_block_empty_start(self):
        block = TimeBlock.objects.create(
            name='Block',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        resp = self.patch_json(
            reverse('todos:update_time_block', args=[block.id]),
            {'start_time': ''}
        )
        self.assertEqual(resp.status_code, 400)

    def test_update_time_block_not_found(self):
        resp = self.patch_json(
            reverse('todos:update_time_block', args=[9999]),
            {'name': 'X'}
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_time_block(self):
        block = TimeBlock.objects.create(
            name='Block',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        resp = self.delete_json(reverse('todos:delete_time_block', args=[block.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TimeBlock.objects.count(), 0)

    def test_delete_time_block_not_found(self):
        resp = self.delete_json(reverse('todos:delete_time_block', args=[9999]))
        self.assertEqual(resp.status_code, 404)


class TaskScheduleTests(TodosViewTestBase):
    """Tests for task schedule CRUD."""

    def test_create_schedule(self):
        task = Task.objects.create(title='T', state=self.state1)
        resp = self.post_json(
            reverse('todos:create_task_schedule', args=[task.id]),
            {
                'start_time': '2026-02-07T09:00:00+00:00',
                'end_time': '2026-02-07T10:00:00+00:00'
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('schedule', data)
        self.assertEqual(TaskSchedule.objects.count(), 1)

    def test_create_schedule_missing_start(self):
        task = Task.objects.create(title='T', state=self.state1)
        resp = self.post_json(
            reverse('todos:create_task_schedule', args=[task.id]),
            {'end_time': '2026-02-07T10:00:00+00:00'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_schedule_missing_end(self):
        task = Task.objects.create(title='T', state=self.state1)
        resp = self.post_json(
            reverse('todos:create_task_schedule', args=[task.id]),
            {'start_time': '2026-02-07T09:00:00+00:00'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_schedule_task_not_found(self):
        resp = self.post_json(
            reverse('todos:create_task_schedule', args=[9999]),
            {
                'start_time': '2026-02-07T09:00:00+00:00',
                'end_time': '2026-02-07T10:00:00+00:00'
            }
        )
        self.assertEqual(resp.status_code, 404)

    def test_update_first_schedule(self):
        task = Task.objects.create(title='T', state=self.state1)
        TaskSchedule.objects.create(
            task=task,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        resp = self.patch_json(
            reverse('todos:update_task_first_schedule', args=[task.id]),
            {'start_time': '2026-02-08T09:00:00+00:00'}
        )
        self.assertEqual(resp.status_code, 200)

    def test_update_first_schedule_no_schedule(self):
        task = Task.objects.create(title='T', state=self.state1)
        resp = self.patch_json(
            reverse('todos:update_task_first_schedule', args=[task.id]),
            {'start_time': '2026-02-08T09:00:00+00:00'}
        )
        self.assertEqual(resp.status_code, 404)

    def test_update_schedule_by_id(self):
        task = Task.objects.create(title='T', state=self.state1)
        schedule = TaskSchedule.objects.create(
            task=task,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        resp = self.patch_json(
            reverse('todos:update_task_schedule', args=[schedule.id]),
            {'end_time': '2026-02-07T12:00:00+00:00'}
        )
        self.assertEqual(resp.status_code, 200)

    def test_update_schedule_not_found(self):
        resp = self.patch_json(
            reverse('todos:update_task_schedule', args=[9999]),
            {'end_time': '2026-02-07T12:00:00+00:00'}
        )
        self.assertEqual(resp.status_code, 404)

    def test_update_schedule_empty_start(self):
        task = Task.objects.create(title='T', state=self.state1)
        schedule = TaskSchedule.objects.create(
            task=task,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        resp = self.patch_json(
            reverse('todos:update_task_schedule', args=[schedule.id]),
            {'start_time': ''}
        )
        self.assertEqual(resp.status_code, 400)

    def test_delete_schedule(self):
        task = Task.objects.create(title='T', state=self.state1)
        schedule = TaskSchedule.objects.create(
            task=task,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        resp = self.delete_json(
            reverse('todos:delete_task_schedule', args=[schedule.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TaskSchedule.objects.count(), 0)

    def test_delete_schedule_not_found(self):
        resp = self.delete_json(reverse('todos:delete_task_schedule', args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_delete_all_schedules(self):
        task = Task.objects.create(title='T', state=self.state1)
        now = timezone.now()
        TaskSchedule.objects.create(task=task, start_time=now, end_time=now + timedelta(hours=1))
        TaskSchedule.objects.create(task=task, start_time=now + timedelta(hours=2), end_time=now + timedelta(hours=3))
        resp = self.delete_json(
            reverse('todos:delete_task_schedules', args=[task.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TaskSchedule.objects.count(), 0)

    def test_delete_all_schedules_task_not_found(self):
        resp = self.delete_json(reverse('todos:delete_task_schedules', args=[9999]))
        self.assertEqual(resp.status_code, 404)


class TaskDetailTemplateTests(TodosViewTestBase):
    """Tests for task detail template CRUD."""

    def test_list_templates(self):
        TaskDetailTemplate.objects.create(name='T1', content='c1')
        resp = self.client.get(reverse('todos:list_templates'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['templates']), 1)

    def test_create_template(self):
        resp = self.post_json(
            reverse('todos:create_template'),
            {'name': 'Daily', 'content': '## Notes'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['template']['name'], 'Daily')

    def test_create_template_auto_order(self):
        TaskDetailTemplate.objects.create(name='T1', content='c1')
        resp = self.post_json(
            reverse('todos:create_template'),
            {'name': 'T2', 'content': 'c2'}
        )
        self.assertEqual(resp.json()['template']['order'], 1)

    def test_create_template_empty_name(self):
        resp = self.post_json(
            reverse('todos:create_template'),
            {'name': '', 'content': 'x'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_update_template(self):
        t = TaskDetailTemplate.objects.create(name='Old', content='old')
        resp = self.patch_json(
            reverse('todos:update_template', args=[t.id]),
            {'name': 'New', 'content': 'new'}
        )
        self.assertEqual(resp.status_code, 200)
        t.refresh_from_db()
        self.assertEqual(t.name, 'New')
        self.assertEqual(t.content, 'new')

    def test_update_template_set_default(self):
        t1 = TaskDetailTemplate.objects.create(name='T1', content='c', is_default=True)
        t2 = TaskDetailTemplate.objects.create(name='T2', content='c')
        self.patch_json(
            reverse('todos:update_template', args=[t2.id]),
            {'is_default': True}
        )
        t1.refresh_from_db()
        t2.refresh_from_db()
        self.assertFalse(t1.is_default)
        self.assertTrue(t2.is_default)

    def test_update_template_not_found(self):
        resp = self.patch_json(
            reverse('todos:update_template', args=[9999]),
            {'name': 'X'}
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_template(self):
        t = TaskDetailTemplate.objects.create(name='T', content='c')
        resp = self.delete_json(reverse('todos:delete_template', args=[t.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TaskDetailTemplate.objects.count(), 0)

    def test_delete_template_not_found(self):
        resp = self.delete_json(reverse('todos:delete_template', args=[9999]))
        self.assertEqual(resp.status_code, 404)


class SavedViewTests(TodosViewTestBase):
    """Tests for saved task view CRUD."""

    def test_list_views(self):
        TaskView.objects.create(name='All', settings={})
        resp = self.client.get(reverse('todos:list_views'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['views']), 1)

    def test_create_view(self):
        resp = self.post_json(
            reverse('todos:create_view'),
            {'name': 'Active', 'settings': {'filter': 'active'}, 'is_default': True}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['view']['name'], 'Active')
        self.assertEqual(data['view']['settings'], {'filter': 'active'})
        self.assertTrue(data['view']['is_default'])

    def test_create_view_empty_name(self):
        resp = self.post_json(
            reverse('todos:create_view'),
            {'name': '', 'settings': {}}
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_view_auto_order(self):
        TaskView.objects.create(name='V1')
        resp = self.post_json(
            reverse('todos:create_view'),
            {'name': 'V2', 'settings': {}}
        )
        self.assertEqual(resp.json()['view']['order'], 1)

    def test_delete_view(self):
        v = TaskView.objects.create(name='V')
        resp = self.delete_json(reverse('todos:delete_view', args=[v.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TaskView.objects.count(), 0)

    def test_delete_view_not_found(self):
        resp = self.delete_json(reverse('todos:delete_view', args=[9999]))
        self.assertEqual(resp.status_code, 404)


class AbandonedTasksTests(TodosViewTestBase):
    """Tests for the process abandoned tasks endpoint."""

    def test_process_abandoned_basic(self):
        # Create a task that's old enough to be abandoned
        task = Task.objects.create(title='Old Task', state=self.state1)
        Task.objects.filter(id=task.id).update(
            updated_at=timezone.now() - timedelta(days=30)
        )
        resp = self.post_json(
            reverse('todos:process_abandoned'),
            {'abandoned_days': 14}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['abandoned_count'], 1)
        self.assertIn(task.id, data['abandoned_task_ids'])

    def test_process_abandoned_creates_state(self):
        """Should auto-create the Abandoned system state."""
        self.post_json(
            reverse('todos:process_abandoned'),
            {'abandoned_days': 14}
        )
        self.assertTrue(TaskState.objects.filter(name='Abandoned', is_system=True).exists())

    def test_process_abandoned_excludes_tags(self):
        tag = TaskTag.objects.create(name='keep')
        task = Task.objects.create(title='Old Task', state=self.state1)
        task.tags.add(tag)
        Task.objects.filter(id=task.id).update(
            updated_at=timezone.now() - timedelta(days=30)
        )
        resp = self.post_json(
            reverse('todos:process_abandoned'),
            {'abandoned_days': 14, 'excluded_tag_ids': [tag.id]}
        )
        self.assertEqual(resp.json()['abandoned_count'], 0)

    def test_process_abandoned_excludes_states(self):
        task = Task.objects.create(title='Old Task', state=self.state1)
        Task.objects.filter(id=task.id).update(
            updated_at=timezone.now() - timedelta(days=30)
        )
        resp = self.post_json(
            reverse('todos:process_abandoned'),
            {'abandoned_days': 14, 'excluded_state_ids': [self.state1.id]}
        )
        self.assertEqual(resp.json()['abandoned_count'], 0)

    def test_process_abandoned_skips_recent_tasks(self):
        Task.objects.create(title='Recent Task', state=self.state1)
        resp = self.post_json(
            reverse('todos:process_abandoned'),
            {'abandoned_days': 14}
        )
        self.assertEqual(resp.json()['abandoned_count'], 0)


class CalendarEventOverrideTests(TodosViewTestBase):
    """Tests for calendar event move and hide."""

    def setUp(self):
        super().setUp()
        self.event = CalendarEvent.objects.create(
            outlook_id='test-event-1',
            subject='Meeting',
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=1),
            is_active=True
        )

    def test_move_calendar_event(self):
        resp = self.post_json(
            reverse('todos:move_calendar_event', args=[self.event.id]),
            {
                'start_time': '2026-02-07T14:00:00+00:00',
                'end_time': '2026-02-07T15:00:00+00:00'
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.event.refresh_from_db()
        self.assertIsNotNone(self.event.override_start)
        self.assertIsNotNone(self.event.override_end)

    def test_move_calendar_event_missing_times(self):
        resp = self.post_json(
            reverse('todos:move_calendar_event', args=[self.event.id]),
            {'start_time': '2026-02-07T14:00:00+00:00'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_move_calendar_event_not_found(self):
        resp = self.post_json(
            reverse('todos:move_calendar_event', args=[9999]),
            {
                'start_time': '2026-02-07T14:00:00+00:00',
                'end_time': '2026-02-07T15:00:00+00:00'
            }
        )
        self.assertEqual(resp.status_code, 404)

    def test_hide_calendar_event(self):
        resp = self.post_json(
            reverse('todos:hide_calendar_event', args=[self.event.id]),
            {}
        )
        self.assertEqual(resp.status_code, 200)
        self.event.refresh_from_db()
        self.assertTrue(self.event.is_hidden)

    def test_hide_calendar_event_not_found(self):
        resp = self.post_json(
            reverse('todos:hide_calendar_event', args=[9999]),
            {}
        )
        self.assertEqual(resp.status_code, 404)


class DoneForTodayTests(TodosViewTestBase):
    """Tests for done for today marking."""

    def test_mark_done_for_today(self):
        task = Task.objects.create(title='T', state=self.state1)
        resp = self.post_json(
            reverse('todos:mark_done_for_today', args=[task.id]),
            {'date': '2026-02-07'}
        )
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        from datetime import date
        self.assertEqual(task.done_for_day, date(2026, 2, 7))

    def test_mark_done_for_today_default_date(self):
        task = Task.objects.create(title='T', state=self.state1)
        resp = self.post_json(
            reverse('todos:mark_done_for_today', args=[task.id]),
            {}
        )
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        self.assertIsNotNone(task.done_for_day)

    def test_mark_done_not_found(self):
        resp = self.post_json(
            reverse('todos:mark_done_for_today', args=[9999]),
            {}
        )
        self.assertEqual(resp.status_code, 404)

    def test_unmark_done_for_today(self):
        from datetime import date
        task = Task.objects.create(title='T', state=self.state1, done_for_day=date.today())
        resp = self.post_json(
            reverse('todos:unmark_done_for_today', args=[task.id]),
            {}
        )
        self.assertEqual(resp.status_code, 200)
        task.refresh_from_db()
        self.assertIsNone(task.done_for_day)

    def test_unmark_done_not_found(self):
        resp = self.post_json(
            reverse('todos:unmark_done_for_today', args=[9999]),
            {}
        )
        self.assertEqual(resp.status_code, 404)


class SerializeTaskTests(TodosViewTestBase):
    """Tests for task serialization via the get_task endpoint."""

    def test_serialize_includes_all_fields(self):
        task = Task.objects.create(title='Full Task', state=self.state1, critical=True)
        tag = TaskTag.objects.create(name='important')
        task.tags.add(tag)
        now = timezone.now()
        TaskSchedule.objects.create(task=task, start_time=now, end_time=now + timedelta(hours=1))

        resp = self.client.get(reverse('todos:get_task', args=[task.id]))
        data = resp.json()['task']
        self.assertEqual(data['title'], 'Full Task')
        self.assertTrue(data['critical'])
        self.assertEqual(data['state_id'], self.state1.id)
        self.assertEqual(data['state_name'], 'Backlog')
        self.assertEqual(len(data['tags']), 1)
        self.assertEqual(data['tags'][0]['name'], 'important')
        self.assertEqual(len(data['schedules']), 1)
        self.assertIsNotNone(data['calendar_start_time'])
        self.assertIsNotNone(data['calendar_end_time'])

    def test_serialize_no_schedule(self):
        task = Task.objects.create(title='Task', state=self.state1)
        resp = self.client.get(reverse('todos:get_task', args=[task.id]))
        data = resp.json()['task']
        self.assertIsNone(data['calendar_start_time'])
        self.assertIsNone(data['calendar_end_time'])
        self.assertEqual(data['schedules'], [])

    def test_serialize_no_state(self):
        task = Task.objects.create(title='Stateless')
        resp = self.client.get(reverse('todos:get_task', args=[task.id]))
        data = resp.json()['task']
        self.assertIsNone(data['state_id'])
        self.assertIsNone(data['state_name'])
