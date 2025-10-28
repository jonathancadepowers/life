"""
Toggl API Client for fetching time tracking data.

This client handles API token authentication and data fetching from the Toggl Track API v9.

Mapping:
- Toggl Projects → Database Projects
- Toggl Tags → Database Goals
"""
import os
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dotenv import load_dotenv

load_dotenv()


class TogglAPIClient:
    """Client for interacting with the Toggl Track API v9."""

    BASE_URL = "https://api.track.toggl.com/api/v9"

    def __init__(self, use_database: bool = True):
        """
        Initialize Toggl API client.

        Args:
            use_database: If True, load credentials from database (with env var fallback).
                         If False, use env vars only.
        """
        self.use_database = use_database
        self.credential = None
        self.api_token = None
        self.workspace_id = None

        # Load credentials from database or environment variables
        if self.use_database:
            self._load_credentials_from_db()
        else:
            # Use environment variables only (for testing or non-database setups)
            self.api_token = os.getenv('TOGGL_API_TOKEN')
            self.workspace_id = os.getenv('TOGGL_WORKSPACE_ID')

        # Validate that we have required credentials
        if not self.api_token:
            raise ValueError(
                "Toggl API token not found. Please ensure it is set in the database "
                "(oauth_integration.APICredential) or in environment variables "
                "(TOGGL_API_TOKEN)."
            )

    def _load_credentials_from_db(self):
        """Load API credentials from the database, with fallback to environment variables."""
        try:
            from oauth_integration.models import APICredential
            self.credential = APICredential.objects.filter(provider='toggl').first()

            if self.credential:
                # Load credentials from database
                self.api_token = self.credential.api_token
                self.workspace_id = self.credential.workspace_id
            else:
                # Fall back to environment variables (for initial setup)
                self.api_token = os.getenv('TOGGL_API_TOKEN')
                self.workspace_id = os.getenv('TOGGL_WORKSPACE_ID')
        except Exception as e:
            # Fall back to environment variables
            self.api_token = os.getenv('TOGGL_API_TOKEN')
            self.workspace_id = os.getenv('TOGGL_WORKSPACE_ID')

    def _make_request(
        self,
        endpoint: str,
        method: str = 'GET',
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Make an authenticated request to the Toggl API.

        Args:
            endpoint: API endpoint (e.g., '/me/time_entries')
            method: HTTP method (default: GET)
            params: Query parameters

        Returns:
            Response JSON data
        """
        url = f"{self.BASE_URL}{endpoint}"

        # Toggl uses API token as username with 'api_token' as password
        auth = (self.api_token, 'api_token')

        response = requests.request(method, url, auth=auth, params=params)
        response.raise_for_status()

        return response.json()

    def get_time_entries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fetch time entries from Toggl API.

        Args:
            start_date: Start date for time entries (defaults to 30 days ago)
            end_date: End date for time entries (defaults to now)

        Returns:
            List of time entry dictionaries
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        params = {
            'start_date': start_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'end_date': end_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
        }

        return self._make_request('/me/time_entries', params=params)

    def get_projects(self) -> List[Dict]:
        """
        Fetch all projects from workspace.

        Returns:
            List of project dictionaries with id and name
        """
        if not self.workspace_id:
            raise ValueError("TOGGL_WORKSPACE_ID must be set in environment variables")

        return self._make_request(f'/workspaces/{self.workspace_id}/projects')
