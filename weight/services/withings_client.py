"""
Withings API Client for fetching weight and health data.

This client handles OAuth 2.0 authentication and data fetching from the Withings API.
"""
import os
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()


class WithingsAPIClient:
    """Client for interacting with the Withings API."""

    BASE_URL = "https://wbsapi.withings.net"
    AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
    TOKEN_URL = f"{BASE_URL}/v2/oauth2"

    def __init__(self):
        self.client_id = os.getenv('WITHINGS_CLIENT_ID')
        self.client_secret = os.getenv('WITHINGS_CLIENT_SECRET')
        self.redirect_uri = os.getenv('WITHINGS_REDIRECT_URI')
        self.access_token = os.getenv('WITHINGS_ACCESS_TOKEN')
        self.refresh_token = os.getenv('WITHINGS_REFRESH_TOKEN')

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "WITHINGS_CLIENT_ID and WITHINGS_CLIENT_SECRET must be set in environment variables"
            )

    def get_authorization_url(self, state: str) -> str:
        """
        Generate the OAuth authorization URL for the user to authenticate.

        Args:
            state: State parameter for security (required, min 8 chars)

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'user.metrics',
            'state': state,
        }

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
            'action': 'requesttoken',
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': self.redirect_uri,
        }

        response = requests.post(self.TOKEN_URL, data=data)
        response.raise_for_status()

        result = response.json()

        if result.get('status') != 0:
            raise ValueError(f"Withings API error: {result}")

        token_data = result['body']
        self.access_token = token_data['access_token']
        self.refresh_token = token_data['refresh_token']

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
            'action': 'requesttoken',
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
        }

        response = requests.post(self.TOKEN_URL, data=data)
        response.raise_for_status()

        result = response.json()

        if result.get('status') != 0:
            raise ValueError(f"Withings API error: {result}")

        token_data = result['body']
        self.access_token = token_data['access_token']
        self.refresh_token = token_data['refresh_token']

        return token_data

    def _make_authenticated_request(
        self,
        endpoint: str,
        params: Dict
    ) -> Dict:
        """
        Make an authenticated request to the Withings API.

        Args:
            endpoint: API endpoint (e.g., '/measure')
            params: Query parameters including 'action'

        Returns:
            Response JSON data
        """
        if not self.access_token:
            raise ValueError("No access token available. Please authenticate first.")

        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }

        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, headers=headers, params=params)

        # If token expired, try to refresh
        if response.status_code == 401:
            print("Access token expired, refreshing...")
            self.refresh_access_token()
            headers['Authorization'] = f'Bearer {self.access_token}'
            response = requests.get(url, headers=headers, params=params)

        response.raise_for_status()
        result = response.json()

        if result.get('status') != 0:
            raise ValueError(f"Withings API error: {result}")

        return result

    def get_weight_measurements(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        offset: int = 0
    ) -> Dict:
        """
        Fetch weight measurements from Withings API.

        Args:
            start_date: Start date for measurements (defaults to 30 days ago)
            end_date: End date for measurements (defaults to now)
            offset: Pagination offset

        Returns:
            Dictionary containing weight measurement records
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        params = {
            'action': 'getmeas',
            'meastype': 1,  # Weight
            'category': 1,  # Real measurements (not objectives)
            'startdate': int(start_date.timestamp()),
            'enddate': int(end_date.timestamp()),
            'offset': offset,
        }

        return self._make_authenticated_request('/measure', params)

    def get_all_weight_measurements(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fetch all weight measurements, handling pagination automatically.

        Args:
            start_date: Start date for measurements
            end_date: End date for measurements

        Returns:
            List of all weight measurement records
        """
        all_measurements = []
        offset = 0

        while True:
            response = self.get_weight_measurements(
                start_date=start_date,
                end_date=end_date,
                offset=offset
            )

            body = response.get('body', {})
            measuregrps = body.get('measuregrps', [])
            all_measurements.extend(measuregrps)

            # Check if there are more results
            more = body.get('more', 0)
            if more == 0:
                break

            offset += len(measuregrps)

        return all_measurements
