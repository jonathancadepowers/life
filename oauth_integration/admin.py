from django.contrib import admin
from .models import OAuthCredential


@admin.register(OAuthCredential)
class OAuthCredentialAdmin(admin.ModelAdmin):
    list_display = ['provider', 'client_id', 'has_tokens', 'token_expires_at', 'updated_at']
    list_filter = ['provider']
    search_fields = ['provider', 'client_id']
    readonly_fields = ['created_at', 'updated_at', 'token_expires_at']

    fieldsets = (
        ('Provider Information', {
            'fields': ('provider', 'redirect_uri')
        }),
        ('OAuth Credentials', {
            'fields': ('client_id', 'client_secret')
        }),
        ('OAuth Tokens', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_tokens(self, obj):
        """Display whether access and refresh tokens are set."""
        return bool(obj.access_token and obj.refresh_token)
    has_tokens.boolean = True
    has_tokens.short_description = 'Has Tokens'
