from django.db import models
from django.utils import timezone


class APICredential(models.Model):
    """
    Store API token credentials for external API integrations.

    This model stores API tokens and related metadata for integrations
    that use simple API token authentication (not OAuth).
    """

    # Provider identification
    provider = models.CharField(
        max_length=50,
        unique=True,
        help_text="API provider name (e.g., 'toggl')"
    )

    # API credentials
    api_token = models.CharField(
        max_length=500,
        help_text="API token/key for authentication"
    )

    # Common metadata fields (provider-specific, nullable for flexibility)
    workspace_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Workspace/organization ID (if applicable)"
    )
    api_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Base API URL (if different from default)"
    )

    # Additional metadata as JSON for provider-specific needs
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional provider-specific metadata"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['provider']
        verbose_name = 'API Credential'
        verbose_name_plural = 'API Credentials'

    def __str__(self):
        return f"{self.provider.title()} API Credentials"


class OAuthCredential(models.Model):
    """
    Store OAuth credentials for external API integrations.

    This model securely stores OAuth tokens and automatically persists
    refreshed tokens, preventing token expiration issues.
    """

    # Provider identification
    provider = models.CharField(
        max_length=50,
        unique=True,
        help_text="OAuth provider name (e.g., 'whoop', 'withings')"
    )

    # OAuth application credentials
    client_id = models.CharField(
        max_length=255,
        help_text="OAuth client ID from the provider"
    )
    client_secret = models.CharField(
        max_length=255,
        help_text="OAuth client secret from the provider"
    )
    redirect_uri = models.CharField(
        max_length=500,
        help_text="OAuth redirect URI for callback"
    )

    # OAuth tokens
    access_token = models.TextField(
        blank=True,
        null=True,
        help_text="Current access token"
    )
    refresh_token = models.TextField(
        blank=True,
        null=True,
        help_text="Refresh token for obtaining new access tokens"
    )
    token_expires_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the access token expires"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['provider']
        verbose_name = 'OAuth Credential'
        verbose_name_plural = 'OAuth Credentials'

    def __str__(self):
        return f"{self.provider.title()} OAuth Credentials"

    def is_token_expired(self):
        """Check if the access token has expired."""
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at

    def update_tokens(self, access_token, refresh_token=None, expires_in=None):
        """
        Update stored tokens and save to database.

        Args:
            access_token: New access token
            refresh_token: New refresh token (optional, keeps existing if not provided)
            expires_in: Token expiry time in seconds (optional)
        """
        self.access_token = access_token

        if refresh_token:
            self.refresh_token = refresh_token

        if expires_in:
            from datetime import timedelta
            self.token_expires_at = timezone.now() + timedelta(seconds=expires_in)

        self.save()
