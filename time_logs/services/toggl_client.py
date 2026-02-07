"""
Toggl API Client for fetching time tracking data.

This client handles API token authentication and data fetching from the Toggl Track API v9.

Mapping:
- Toggl Projects → Database Projects
- Toggl Tags → Database Goals
"""
import logging
import os
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

_WORKSPACE_ID_ERROR = "TOGGL_WORKSPACE_ID must be set in environment variables"


class TogglAPIClient:
    """Client for interacting with the Toggl Track API v9 and Reports API v3."""

    BASE_URL = "https://api.track.toggl.com/api/v9"
    REPORTS_BASE_URL = "https://api.track.toggl.com/reports/api/v3"

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
        except Exception:
            # Fall back to environment variables
            logger.debug("Could not load Toggl credentials from database, falling back to environment variables")
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

        response = requests.request(method, url, auth=auth, params=params, timeout=30)
        response.raise_for_status()

        return response.json()

    def get_current_time_entry(self) -> Optional[Dict]:
        """
        Fetch the currently running time entry.

        Returns:
            Dictionary with running time entry, or None if no timer is running
        """
        try:
            result = self._make_request('/me/time_entries/current')
            # If no timer is running, the API returns None or empty dict
            if result and result.get('id'):
                return result
            return None
        except Exception:
            # If there's an error or no running timer, return None
            logger.debug("Could not fetch current time entry from Toggl, returning None")
            return None

    def get_time_entries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fetch time entries from Toggl Reports API v3 plus any running timer.

        Uses workspace-specific Reports API which has 240 req/hour limit (for Starter plans)
        instead of the /me endpoint which has only 30 req/hour limit.

        Also fetches the current running timer from the Track API to include active time.

        Args:
            start_date: Start date for time entries (defaults to 30 days ago)
            end_date: End date for time entries (defaults to now)

        Returns:
            List of time entry dictionaries including any running timer
        """
        if not self.workspace_id:
            raise ValueError(_WORKSPACE_ID_ERROR)

        if start_date is None:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now(timezone.utc)

        # Reports API uses different URL and POST method
        url = f"{self.REPORTS_BASE_URL}/workspace/{self.workspace_id}/search/time_entries"

        # Reports API expects JSON payload with start_date and end_date
        payload = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
        }

        # Toggl uses API token as username with 'api_token' as password
        auth = (self.api_token, 'api_token')

        response = requests.post(url, json=payload, auth=auth, timeout=30)
        response.raise_for_status()

        # Fetch tags to map tag IDs to tag names
        # The old API returned tag names, but Reports API returns tag IDs
        tags_list = self.get_tags()
        tag_id_to_name = {tag['id']: tag['name'] for tag in tags_list}

        # Reports API returns data in a grouped format with nested time_entries
        # We need to flatten this to match the old API format
        grouped_entries = response.json()
        flattened_entries = []

        for group in grouped_entries:
            project_id = group.get('project_id')
            tag_ids = group.get('tag_ids', [])

            # Convert tag IDs to tag names to match old API format
            tag_names = [tag_id_to_name.get(tag_id, str(tag_id)) for tag_id in tag_ids]

            # Each group contains an array of time_entries
            for entry in group.get('time_entries', []):
                # Flatten the structure to match the old API format
                flattened_entry = {
                    'id': entry.get('id'),
                    'project_id': project_id,
                    'tags': tag_names,  # Use tag names instead of tag IDs
                    'duration': entry.get('seconds'),  # Map seconds to duration
                    'start': entry.get('start'),
                    'stop': entry.get('stop'),
                }
                flattened_entries.append(flattened_entry)

        # Fetch the currently running timer (if any) from Track API
        running_entry = self.get_current_time_entry()
        if running_entry:
            # Convert running entry to match our format
            # Running timers have negative duration in the Track API
            running_flattened = {
                'id': running_entry.get('id'),
                'project_id': running_entry.get('project_id') or running_entry.get('pid'),
                'tags': running_entry.get('tags', []),
                'duration': running_entry.get('duration', 0),  # Negative for running timers
                'start': running_entry.get('start'),
                'stop': running_entry.get('stop'),
            }
            flattened_entries.append(running_flattened)

        return flattened_entries

    def get_tags(self) -> List[Dict]:
        """
        Fetch all tags from workspace.

        Returns:
            List of tag dictionaries with id and name
        """
        if not self.workspace_id:
            raise ValueError(_WORKSPACE_ID_ERROR)

        return self._make_request(f'/workspaces/{self.workspace_id}/tags')

    def get_projects(self) -> List[Dict]:
        """
        Fetch all projects from workspace.

        Returns:
            List of project dictionaries with id and name
        """
        if not self.workspace_id:
            raise ValueError(_WORKSPACE_ID_ERROR)

        return self._make_request(f'/workspaces/{self.workspace_id}/projects')
