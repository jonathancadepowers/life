from django.urls import path
from . import views

app_name = 'todos'

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('api/create/', views.create_task, name='create_task'),
    path('api/<int:task_id>/update/', views.update_task, name='update_task'),
    path('api/<int:task_id>/delete/', views.delete_task, name='delete_task'),
]
