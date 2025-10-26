from django.contrib import admin
from .models import WeighIn, OAuthCredential


@admin.register(OAuthCredential)
class OAuthCredentialAdmin(admin.ModelAdmin):
    list_display = (
        'service',
        'token_expires_at',
        'updated_at',
    )
    list_filter = ('service',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Service', {
            'fields': ('service',)
        }),
        ('Tokens', {
            'fields': (
                'access_token',
                'refresh_token',
                'token_expires_at',
            )
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(WeighIn)
class WeighInAdmin(admin.ModelAdmin):
    list_display = (
        'measurement_time',
        'weight',
        'source',
        'source_id',
    )
    list_filter = ('source', 'measurement_time')
    search_fields = ('source', 'source_id')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'measurement_time'

    fieldsets = (
        ('Source Information', {
            'fields': ('source', 'source_id')
        }),
        ('Measurement', {
            'fields': (
                'measurement_time',
                'weight',
            )
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
