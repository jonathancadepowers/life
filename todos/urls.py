from django.urls import path
from . import views

app_name = 'todos'

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('api/create/', views.create_task, name='create_task'),
    path('api/<int:task_id>/', views.get_task, name='get_task'),
    path('api/<int:task_id>/update/', views.update_task, name='update_task'),
    path('api/<int:task_id>/delete/', views.delete_task, name='delete_task'),
    path('api/states/', views.list_states, name='list_states'),
    path('api/states/create/', views.create_state, name='create_state'),
    path('api/states/<int:state_id>/update/', views.update_state, name='update_state'),
    path('api/states/<int:state_id>/delete/', views.delete_state, name='delete_state'),
    path('api/states/<int:state_id>/info/', views.get_state_info, name='get_state_info'),
    path('api/states/reorder/', views.reorder_states, name='reorder_states'),
    path('api/tasks/reorder/', views.reorder_tasks, name='reorder_tasks'),
    path('api/tags/', views.list_tags, name='list_tags'),
    path('api/tags/create/', views.create_tag, name='create_tag'),
    path('api/tags/<int:tag_id>/delete/', views.delete_tag, name='delete_tag'),
    path('api/<int:task_id>/tags/add/', views.add_tag_to_task, name='add_tag_to_task'),
    path('api/<int:task_id>/tags/remove/', views.remove_tag_from_task, name='remove_tag_from_task'),
    # Time blocks
    path('api/time-blocks/create/', views.create_time_block, name='create_time_block'),
    path('api/time-blocks/<int:block_id>/update/', views.update_time_block, name='update_time_block'),
    path('api/time-blocks/<int:block_id>/delete/', views.delete_time_block, name='delete_time_block'),
    # Task schedules
    path('api/<int:task_id>/schedules/create/', views.create_task_schedule, name='create_task_schedule'),
    path('api/schedules/<int:schedule_id>/update/', views.update_task_schedule, name='update_task_schedule'),
    path('api/schedules/<int:schedule_id>/delete/', views.delete_task_schedule, name='delete_task_schedule'),
]
