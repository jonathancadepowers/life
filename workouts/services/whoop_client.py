"""
Whoop API Client for fetching workout and health data.

This client handles OAuth 2.0 authentication and data fetching from the Whoop API v2.
"""
import os
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()


class WhoopAPIClient:
    """Client for interacting with the Whoop API v2."""

    BASE_URL = "https://api.prod.whoop.com"
    AUTH_URL = f"{BASE_URL}/oauth/oauth2/auth"
    TOKEN_URL = f"{BASE_URL}/oauth/oauth2/token"

    def __init__(self):
        # Try to load from database first, fall back to environment variables
        self._load_credentials()

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET must be set in environment variables or database"
            )

    def _load_credentials(self):
        """Load OAuth credentials from database or environment variables."""
        try:
            from oauth_integration.models import OAuthCredential
            cred = OAuthCredential.objects.filter(provider='whoop').first()

            if cred:
                self.client_id = cred.client_id
                self.client_secret = cred.client_secret
                self.redirect_uri = cred.redirect_uri
                self.access_token = cred.access_token
                self.refresh_token = cred.refresh_token
                self._db_credential = cred
                return
        except Exception:
            # Database not available or model doesn't exist yet
            pass

        # Fall back to environment variables
        self.client_id = os.getenv('WHOOP_CLIENT_ID')
        self.client_secret = os.getenv('WHOOP_CLIENT_SECRET')
        self.redirect_uri = os.getenv('WHOOP_REDIRECT_URI')
        self.access_token = os.getenv('WHOOP_ACCESS_TOKEN')
        self.refresh_token = os.getenv('WHOOP_REFRESH_TOKEN')
        self._db_credential = None

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate the OAuth authorization URL for the user to authenticate.

        Args:
            state: Optional state parameter for security

        Returns:
            Authorization URL to redirect user to
        """
        scopes = [
            'offline',  # For refresh token
            'read:profile',
            'read:workout',
            'read:cycles',
            'read:recovery',
            'read:sleep',
        ]

        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(scopes),
        }

        if state:
            params['state'] = state

        query_string = urlencode(params)
        return f"{self.AUTH_URL}?{query_string}"

    def exchange_code_for_token(self, code: str) -> Dict:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dictionary containing tokens and expiry information
        """
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
        }

        response = requests.post(self.TOKEN_URL, data=data)
        response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data['access_token']
        self.refresh_token = token_data.get('refresh_token')

        return token_data

    def refresh_access_token(self) -> Dict:
        """
        Refresh the access token using the refresh token.

        Returns:
            Dictionary containing new tokens and expiry information
        """
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'offline read:profile read:workout read:cycles read:recovery read:sleep',
        }

        response = requests.post(self.TOKEN_URL, data=data)

        # Check for expired/invalid refresh token
        if response.status_code == 400:
            raise ValueError(
                "Whoop refresh token expired or invalid. Please re-authenticate by running: "
                "python manage.py whoop_auth"
            )

        response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data['access_token']
        if 'refresh_token' in token_data:
            self.refresh_token = token_data['refresh_token']

        # Save updated tokens to database if using database credentials
        if self._db_credential:
            self._db_credential.update_tokens(
                access_token=self.access_token,
                refresh_token=self.refresh_token,
                expires_in=token_data.get('expires_in')
            )

        return token_data

    def _make_authenticated_request(
        self,
        endpoint: str,
        method: str = 'GET',
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Make an authenticated request to the Whoop API.

        Args:
            endpoint: API endpoint (e.g., '/developer/v2/activity/workout')
            method: HTTP method (default: GET)
            params: Query parameters

        Returns:
            Response JSON data
        """
        # If no access token but we have a refresh token, use it to get a new access token
        if not self.access_token and self.refresh_token:
            print("No access token found, but refresh token exists. Refreshing...")
            self.refresh_access_token()

        # If still no access token, authentication is required
        if not self.access_token:
            raise ValueError("No access token available. Please authenticate first.")

        # Proactively refresh token if expired (check database expiration)
        if self._db_credential and self._db_credential.is_token_expired():
            print("Access token expired (proactive check), refreshing...")
            self.refresh_access_token()

        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }

        url = f"{self.BASE_URL}{endpoint}"
        response = requests.request(method, url, headers=headers, params=params)

        # If token expired, try to refresh (fallback for edge cases)
        if response.status_code == 401:
            print("Access token expired (401 error), refreshing...")
            self.refresh_access_token()
            headers['Authorization'] = f'Bearer {self.access_token}'
            response = requests.request(method, url, headers=headers, params=params)

        response.raise_for_status()
        return response.json()

    def get_workouts(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 25,
        next_token: Optional[str] = None
    ) -> Dict:
        """
        Fetch workouts from Whoop API.

        Args:
            start_date: Start date for workout filter (defaults to 30 days ago)
            end_date: End date for workout filter (defaults to now)
            limit: Number of workouts to fetch (max 25 per page)
            next_token: Pagination token for next page

        Returns:
            Dictionary containing workout records and pagination info
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        params = {
            'start': start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'end': end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'limit': limit,
        }

        if next_token:
            params['nextToken'] = next_token

        return self._make_authenticated_request(
            '/developer/v2/activity/workout',
            params=params
        )

    def get_all_workouts(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fetch all workouts, handling pagination automatically.

        Args:
            start_date: Start date for workout filter
            end_date: End date for workout filter

        Returns:
            List of all workout records
        """
        all_workouts = []
        next_token = None

        while True:
            response = self.get_workouts(
                start_date=start_date,
                end_date=end_date,
                next_token=next_token
            )

            records = response.get('records', [])
            all_workouts.extend(records)

            next_token = response.get('next_token')
            if not next_token:
                break

        return all_workouts

    def get_user_profile(self) -> Dict:
        """
        Fetch the authenticated user's profile information.

        Returns:
            Dictionary containing user profile data
        """
        return self._make_authenticated_request('/developer/v2/user/profile/basic')
