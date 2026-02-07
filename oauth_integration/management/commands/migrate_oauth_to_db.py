"""
Django management command to migrate OAuth credentials from environment variables to database.

This command reads OAuth credentials from environment variables and stores them in the
OAuthCredential model, enabling automatic token refresh persistence.

Usage:
    python manage.py migrate_oauth_to_db
"""
from django.core.management.base import BaseCommand
from oauth_integration.models import OAuthCredential
import os


class Command(BaseCommand):
    help = 'Migrate OAuth credentials from environment variables to database'

    def handle(self, *_args, **_options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  MIGRATE OAUTH CREDENTIALS TO DATABASE'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')

        providers = [
            {
                'name': 'whoop',
                'client_id_key': 'WHOOP_CLIENT_ID',
                'client_secret_key': 'WHOOP_CLIENT_SECRET',
                'redirect_uri_key': 'WHOOP_REDIRECT_URI',
                'access_token_key': 'WHOOP_ACCESS_TOKEN',
                'refresh_token_key': 'WHOOP_REFRESH_TOKEN',
            },
            {
                'name': 'withings',
                'client_id_key': 'WITHINGS_CLIENT_ID',
                'client_secret_key': 'WITHINGS_CLIENT_SECRET',
                'redirect_uri_key': 'WITHINGS_REDIRECT_URI',
                'access_token_key': 'WITHINGS_ACCESS_TOKEN',
                'refresh_token_key': 'WITHINGS_REFRESH_TOKEN',
            },
        ]

        migrated = 0
        skipped = 0

        for provider_config in providers:
            provider_name = provider_config['name']
            self.stdout.write(f"\nProcessing {provider_name.upper()}...")

            # Get credentials from environment
            client_id = os.getenv(provider_config['client_id_key'])
            client_secret = os.getenv(provider_config['client_secret_key'])
            redirect_uri = os.getenv(provider_config['redirect_uri_key'])
            access_token = os.getenv(provider_config['access_token_key'])
            refresh_token = os.getenv(provider_config['refresh_token_key'])

            # Check if credentials exist
            if not client_id or not client_secret:
                self.stdout.write(self.style.WARNING(
                    "  ⊘ Skipped: Missing client_id or client_secret in environment variables"
                ))
                skipped += 1
                continue

            # Create or update credential in database
            _, created = OAuthCredential.objects.update_or_create(
                provider=provider_name,
                defaults={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri or '',
                    'access_token': access_token or '',
                    'refresh_token': refresh_token or '',
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(
                    "  ✓ Created new credential entry"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    "  ✓ Updated existing credential entry"
                ))

            # Show token status
            if access_token and refresh_token:
                self.stdout.write(f"    • Access token: {'*' * 20}...{access_token[-8:]}")
                self.stdout.write(f"    • Refresh token: {'*' * 20}...{refresh_token[-8:]}")
            else:
                self.stdout.write(self.style.WARNING(
                    f"    ⚠ No tokens found - you'll need to run {provider_name}_auth"
                ))

            migrated += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  MIGRATION SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f"Migrated: {migrated} provider(s)")
        self.stdout.write(f"Skipped:  {skipped} provider(s)")
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            '✓ OAuth credentials are now stored in the database!'
        ))
        self.stdout.write(self.style.SUCCESS(
            '  Tokens will automatically persist when refreshed.'
        ))
        self.stdout.write('')
