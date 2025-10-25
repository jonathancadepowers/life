"""
Toggl API Client for fetching time tracking data.

This client handles API token authentication and data fetching from the Toggl Track API v9.
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

    def __init__(self):
        self.api_token = os.getenv('TOGGL_API_TOKEN')
        self.workspace_id = os.getenv('TOGGL_WORKSPACE_ID')

        if not self.api_token:
            raise ValueError(
                "TOGGL_API_TOKEN must be set in environment variables"
            )

        # Cache for project -> client mapping
        self._project_client_map = {}

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
            List of project dictionaries including client_id mapping
        """
        if not self.workspace_id:
            raise ValueError("TOGGL_WORKSPACE_ID must be set in environment variables")

        return self._make_request(f'/workspaces/{self.workspace_id}/projects')

    def build_project_client_map(self) -> Dict[int, Optional[int]]:
        """
        Build a mapping of project_id -> client_id.

        Returns:
            Dictionary mapping project IDs to client IDs
        """
        if not self._project_client_map:
            projects = self.get_projects()
            self._project_client_map = {
                project['id']: project.get('client_id')
                for project in projects
            }

        return self._project_client_map

    def get_time_entries_with_client_mapping(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fetch time entries and enrich with client_id mapping.

        Args:
            start_date: Start date for time entries
            end_date: End date for time entries

        Returns:
            List of time entries with client_id added from project mapping
        """
        # Build project -> client mapping
        project_client_map = self.build_project_client_map()

        # Fetch time entries
        time_entries = self.get_time_entries(start_date, end_date)

        # Enrich with client_id
        for entry in time_entries:
            project_id = entry.get('project_id')
            if project_id:
                entry['client_id'] = project_client_map.get(project_id)
            else:
                entry['client_id'] = None

        return time_entries
