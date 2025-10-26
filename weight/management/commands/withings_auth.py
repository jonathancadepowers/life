"""
Django management command to authenticate with Withings API.

This command helps you get your initial access and refresh tokens.

Usage:
    python manage.py withings_auth
"""
from django.core.management.base import BaseCommand
from weight.services.withings_client import WithingsAPIClient
import os
import secrets


class Command(BaseCommand):
    help = 'Authenticate with Withings API and obtain access tokens'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Withings API Authentication'))
        self.stdout.write('=' * 50)

        try:
            client = WithingsAPIClient()

            # Generate a secure random state parameter (required by Withings)
            state = secrets.token_urlsafe(16)

            # Generate authorization URL
            auth_url = client.get_authorization_url(state=state)

            self.stdout.write('\nStep 1: Visit this URL in your browser:')
            self.stdout.write(self.style.HTTP_INFO(auth_url))

            self.stdout.write('\nStep 2: Log in to Withings and authorize the application')
            self.stdout.write('Step 3: After authorization, you will be redirected to your redirect URI')
            self.stdout.write('        with a "code" parameter in the URL')
            self.stdout.write('        (You may see a 404 error page - that\'s OK! Just copy the code from the URL)')

            self.stdout.write('\nStep 4: Copy the authorization code from the URL')
            self.stdout.write('        Example URL: http://localhost:8000/withings/callback?code=ABC123...')
            self.stdout.write('        You want to copy just the part after "code="\n')
            auth_code = input('\nPaste the authorization code here: ').strip()

            if not auth_code:
                self.stdout.write(self.style.ERROR('No authorization code provided'))
                return

            # Exchange code for tokens
            self.stdout.write('\nExchanging code for tokens...')
            token_data = client.exchange_code_for_token(auth_code)

            # Display token information
            self.stdout.write(self.style.SUCCESS('\n✓ Authentication successful!'))
            self.stdout.write('\n✓ Tokens saved to database automatically')

            self.stdout.write('\nToken Information:')
            self.stdout.write('=' * 50)
            self.stdout.write(f'Access Token: {token_data["access_token"][:20]}...')
            self.stdout.write(f'Refresh Token: {token_data["refresh_token"][:20]}...')
            self.stdout.write(f'Expires in: {token_data.get("expires_in", 10800)} seconds ({token_data.get("expires_in", 10800) / 3600:.1f} hours)')
            self.stdout.write('=' * 50)

            self.stdout.write(self.style.SUCCESS(
                '\nYou can now run: python manage.py sync_withings'
            ))

            self.stdout.write(self.style.WARNING(
                '\nNote: Tokens are stored in the database and will be automatically'
                '\nrefreshed when they expire. You no longer need to manually update'
                '\nenvironment variables with new tokens.'
            ))

        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'Configuration error: {e}'))
            self.stdout.write(self.style.WARNING(
                '\nMake sure you have set up your Withings API credentials in .env file:'
            ))
            self.stdout.write('  WITHINGS_CLIENT_ID')
            self.stdout.write('  WITHINGS_CLIENT_SECRET')
            self.stdout.write('  WITHINGS_REDIRECT_URI')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during authentication: {e}'))
            raise
