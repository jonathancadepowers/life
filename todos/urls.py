from django.urls import path
from . import views

app_name = 'todos'

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('api/create/', views.create_task, name='create_task'),
    path('api/<int:task_id>/update/', views.update_task, name='update_task'),
    path('api/<int:task_id>/delete/', views.delete_task, name='delete_task'),
    path('api/contexts/', views.list_contexts, name='list_contexts'),
    path('api/contexts/create/', views.create_context, name='create_context'),
    path('api/contexts/<int:context_id>/delete/', views.delete_context, name='delete_context'),
]
