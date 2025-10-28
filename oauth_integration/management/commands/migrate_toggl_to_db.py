"""
Django management command to migrate Toggl API credentials from environment variables to database.

Usage:
    python manage.py migrate_toggl_to_db
"""
import os
from django.core.management.base import BaseCommand
from oauth_integration.models import APICredential


class Command(BaseCommand):
    help = 'Migrate Toggl API credentials from environment variables to database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  MIGRATE TOGGL CREDENTIALS TO DATABASE'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # Load from environment variables
        api_token = os.getenv('TOGGL_API_TOKEN')
        workspace_id = os.getenv('TOGGL_WORKSPACE_ID')

        if not api_token:
            self.stdout.write(self.style.ERROR('\n✗ Error: TOGGL_API_TOKEN not found in environment variables'))
            self.stdout.write('Please set TOGGL_API_TOKEN in your .env file or environment')
            return

        # Check if already exists in database
        existing = APICredential.objects.filter(provider='toggl').first()

        if existing:
            self.stdout.write(self.style.WARNING('\n⚠ Toggl credentials already exist in database'))
            self.stdout.write(f'Current API token: {existing.api_token[:10]}...')
            self.stdout.write(f'Current workspace ID: {existing.workspace_id}')

            # Ask if they want to update
            confirm = input('\nUpdate with environment variable values? [y/N]: ')
            if confirm.lower() != 'y':
                self.stdout.write(self.style.WARNING('\nCancelled. No changes made.'))
                return

            # Update existing
            existing.api_token = api_token
            existing.workspace_id = workspace_id or existing.workspace_id
            existing.save()

            self.stdout.write(self.style.SUCCESS('\n✓ Updated Toggl credentials in database'))
        else:
            # Create new
            APICredential.objects.create(
                provider='toggl',
                api_token=api_token,
                workspace_id=workspace_id
            )
            self.stdout.write(self.style.SUCCESS('\n✓ Created Toggl credentials in database'))

        self.stdout.write('\nCredentials stored:')
        self.stdout.write(f'  Provider: toggl')
        self.stdout.write(f'  API Token: {api_token[:10]}...')
        self.stdout.write(f'  Workspace ID: {workspace_id}')
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✓ Migration complete!'))
        self.stdout.write('=' * 60)
        self.stdout.write('\nYou can now remove TOGGL_API_TOKEN and TOGGL_WORKSPACE_ID')
        self.stdout.write('from your environment variables and Heroku config.')
