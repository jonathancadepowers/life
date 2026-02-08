"""
Django management command to authenticate with Whoop API.

This command helps you get your initial access and refresh tokens.

Usage:
    python manage.py whoop_auth
"""
from django.core.management.base import BaseCommand
from workouts.services.whoop_client import WhoopAPIClient
import secrets


class Command(BaseCommand):
    help = 'Authenticate with Whoop API and obtain access tokens'

    def handle(self, *_args, **_options):
        self.stdout.write(self.style.SUCCESS('Whoop API Authentication'))
        self.stdout.write('=' * 50)

        try:
            client = WhoopAPIClient()

            # Generate a secure random state parameter (required by Whoop)
            state = secrets.token_urlsafe(16)

            # Generate authorization URL
            auth_url = client.get_authorization_url(state=state)

            self.stdout.write('\nStep 1: Visit this URL in your browser:')
            self.stdout.write(self.style.HTTP_INFO(auth_url))

            self.stdout.write('\nStep 2: Log in to Whoop and authorize the application')
            self.stdout.write('Step 3: After authorization, you will be redirected to your redirect URI')
            self.stdout.write('        with a "code" parameter in the URL')
            self.stdout.write('        (You may see a 404 error page - that\'s OK! Just copy the code from the URL)')

            self.stdout.write('\nStep 4: Copy the authorization code from the URL')
            self.stdout.write('        Example URL: http://localhost:8000/whoop/callback?code=ABC123...')
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
            self.stdout.write('\nAdd these to your .env file:')
            self.stdout.write('=' * 50)
            self.stdout.write(f'WHOOP_ACCESS_TOKEN={token_data["access_token"]}')
            if 'refresh_token' in token_data:
                self.stdout.write(f'WHOOP_REFRESH_TOKEN={token_data["refresh_token"]}')
            self.stdout.write(f'WHOOP_TOKEN_EXPIRES_AT={token_data.get("expires_in", 3600)}')
            self.stdout.write('=' * 50)

            self.stdout.write('\nToken expires in: {} seconds ({} hour)'.format(
                token_data.get('expires_in', 3600),
                token_data.get('expires_in', 3600) / 3600
            ))

            self.stdout.write(self.style.SUCCESS(
                '\nYou can now run: python manage.py sync_whoop'
            ))

        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'Configuration error: {e}'))
            self.stdout.write(self.style.WARNING(
                '\nMake sure you have set up your Whoop API credentials in .env file:'
            ))
            self.stdout.write('  WHOOP_CLIENT_ID')
            self.stdout.write('  WHOOP_CLIENT_SECRET')
            self.stdout.write('  WHOOP_REDIRECT_URI')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during authentication: {e}'))
            raise
