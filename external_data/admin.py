from django.contrib import admin
from .models import WhoopSportId


@admin.register(WhoopSportId)
class WhoopSportIdAdmin(admin.ModelAdmin):
    list_display = ('sport_id', 'sport_name')
    search_fields = ('sport_id', 'sport_name')
    ordering = ('sport_id',)

    def has_add_permission(self, _request):
        # Prevent manual additions - data should be populated via management command
        return False

    def has_delete_permission(self, _request, _obj=None):
        # Prevent deletions - reference data
        return False
