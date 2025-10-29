from django.urls import path
from . import views

urlpatterns = [
    path('', views.set_agenda, name='set_agenda'),
    path('api/goals/', views.get_goals_for_project, name='get_goals_for_project'),
    path('api/sync-toggl/', views.sync_toggl_projects_goals, name='sync_toggl_projects_goals'),
    path('api/save-agenda/', views.save_agenda, name='save_agenda'),
    path('api/toggl-time-today/', views.get_toggl_time_today, name='get_toggl_time_today'),
    path('api/available-dates/', views.get_available_agenda_dates, name='get_available_agenda_dates'),
    path('api/agenda-for-date/', views.get_agenda_for_date, name='get_agenda_for_date'),
    path('api/save-target-score/', views.save_target_score, name='save_target_score'),
    path('api/create-objective/', views.create_objective, name='create_objective'),
    path('api/update-objective/', views.update_objective, name='update_objective'),
    path('api/delete-objective/', views.delete_objective, name='delete_objective'),
]
