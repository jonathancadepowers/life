from django.urls import path
from . import views

urlpatterns = [
    path('', views.set_agenda, name='set_agenda'),
    path('api/goals/', views.get_goals_for_project, name='get_goals_for_project'),
    path('api/targets/', views.get_targets_for_goal, name='get_targets_for_goal'),
    path('api/save-agenda/', views.save_agenda, name='save_agenda'),
    path('api/toggl-time-today/', views.get_toggl_time_today, name='get_toggl_time_today'),
    path('api/available-dates/', views.get_available_agenda_dates, name='get_available_agenda_dates'),
    path('api/agenda-for-date/', views.get_agenda_for_date, name='get_agenda_for_date'),
    path('api/save-target-score/', views.save_target_score, name='save_target_score'),
]
