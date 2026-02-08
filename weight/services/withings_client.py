"""
Withings API Client for fetching weight and health data.

This client handles OAuth 2.0 authentication and data fetching from the Withings API.
"""

import os
import requests
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class WithingsAPIClient:
    """Client for interacting with the Withings API."""

    BASE_URL = "https://wbsapi.withings.net"
    AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
    TOKEN_URL = f"{BASE_URL}/v2/oauth2"

    def __init__(self, use_database: bool = True):
        """
        Initialize Withings API client.

        Args:
            use_database: If True, load credentials from database (with env var fallback).
                         If False, use env vars only.
        """
        self.use_database = use_database
        self.credential = None
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.access_token = None
        self.refresh_token = None

        # Load all credentials from database or environment variables
        if self.use_database:
            self._load_credentials_from_db()
        else:
            # Use environment variables only (for testing or non-database setups)
            self.client_id = os.getenv("WITHINGS_CLIENT_ID")
            self.client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
            self.redirect_uri = os.getenv("WITHINGS_REDIRECT_URI")
            self.access_token = os.getenv("WITHINGS_ACCESS_TOKEN")
            self.refresh_token = os.getenv("WITHINGS_REFRESH_TOKEN")

        # Validate that we have at least client credentials
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Withings client credentials not found. Please ensure they are set in the database "
                "(oauth_integration.OAuthCredential) or in environment variables "
                "(WITHINGS_CLIENT_ID, WITHINGS_CLIENT_SECRET)."
            )

    def _load_credentials_from_db(self):
        """Load OAuth credentials from the database, with fallback to environment variables."""
        try:
            from oauth_integration.models import OAuthCredential

            self.credential = OAuthCredential.objects.filter(provider="withings").first()

            if self.credential:
                # Load all credentials from database
                self.client_id = self.credential.client_id
                self.client_secret = self.credential.client_secret
                self.redirect_uri = self.credential.redirect_uri
                self.access_token = self.credential.access_token
                self.refresh_token = self.credential.refresh_token
                logger.info("Loaded Withings credentials from database")
            else:
                # Fall back to environment variables (for initial setup)
                self.client_id = os.getenv("WITHINGS_CLIENT_ID")
                self.client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
                self.redirect_uri = os.getenv("WITHINGS_REDIRECT_URI")
                self.access_token = os.getenv("WITHINGS_ACCESS_TOKEN")
                self.refresh_token = os.getenv("WITHINGS_REFRESH_TOKEN")
                logger.warning("No Withings credentials in database, using environment variables")
        except Exception as e:
            logger.error(f"Error loading credentials from database: {e}")
            # Fall back to environment variables
            self.client_id = os.getenv("WITHINGS_CLIENT_ID")
            self.client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
            self.redirect_uri = os.getenv("WITHINGS_REDIRECT_URI")
            self.access_token = os.getenv("WITHINGS_ACCESS_TOKEN")
            self.refresh_token = os.getenv("WITHINGS_REFRESH_TOKEN")

    def _save_credentials_to_db(self, access_token: str, refresh_token: str, expires_in: int):
        """Save OAuth credentials to the database."""
        if not self.use_database:
            return

        try:
            from oauth_integration.models import OAuthCredential
            from django.utils import timezone

            token_expires_at = timezone.now() + timedelta(seconds=expires_in)

            OAuthCredential.objects.update_or_create(
                provider="withings",
                defaults={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expires_at": token_expires_at,
                },
            )
            logger.info("Saved Withings credentials to database")
        except Exception as e:
            logger.error(f"Error saving credentials to database: {e}")

    def get_authorization_url(self, state: str) -> str:
        """
        Generate the OAuth authorization URL for the user to authenticate.

        Args:
            state: State parameter for security (required, min 8 chars)

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user.metrics",
            "state": state,
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
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        response = requests.post(self.TOKEN_URL, data=data, timeout=30)
        response.raise_for_status()

        result = response.json()

        if result.get("status") != 0:
            raise ValueError(f"Withings API error: {result}")

        token_data = result["body"]
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data["refresh_token"]

        # Save to database
        expires_in = token_data.get("expires_in", 10800)  # Default 3 hours
        self._save_credentials_to_db(self.access_token, self.refresh_token, expires_in)

        return token_data

    def refresh_access_token(self) -> Dict:
        """
        Refresh the access token using the refresh token.

        Returns:
            Dictionary containing new tokens and expiry information

        Raises:
            ValueError: If refresh token is invalid or refresh fails
        """
        if not self.refresh_token:
            raise ValueError("No refresh token available. Please run: python manage.py withings_auth")

        data = {
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }

        response = requests.post(self.TOKEN_URL, data=data, timeout=30)
        response.raise_for_status()

        result = response.json()

        if result.get("status") != 0:
            error_msg = result.get("error", "Unknown error")
            if "invalid refresh_token" in str(error_msg).lower() or result.get("status") == 401:
                raise ValueError(
                    "Withings refresh token expired or invalid. Please re-authenticate by running: "
                    "python manage.py withings_auth"
                )
            raise ValueError(f"Withings API error: {result}")

        token_data = result["body"]
        self.access_token = token_data["access_token"]
        # Only update refresh token if a new one is provided (token rotation)
        if "refresh_token" in token_data:
            self.refresh_token = token_data["refresh_token"]

        # Save to database
        expires_in = token_data.get("expires_in", 10800)  # Default 3 hours
        self._save_credentials_to_db(self.access_token, self.refresh_token, expires_in)
        logger.info("Successfully refreshed Withings access token")

        return token_data

    def _make_authenticated_request(self, endpoint: str, params: Dict) -> Dict:
        """
        Make an authenticated request to the Withings API.

        Args:
            endpoint: API endpoint (e.g., '/measure')
            params: Query parameters including 'action'

        Returns:
            Response JSON data
        """
        # If no access token but we have a refresh token, use it to get a new access token
        if not self.access_token and self.refresh_token:
            logger.info("No access token found, but refresh token exists. Refreshing...")
            self.refresh_access_token()

        # If still no access token, authentication is required
        if not self.access_token:
            raise ValueError("No access token available. Please authenticate first.")

        # Proactively refresh token if expired (check database expiration)
        if self.credential and self.credential.is_token_expired():
            logger.info("Access token expired (proactive check), refreshing...")
            self.refresh_access_token()

        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, headers=headers, params=params, timeout=30)

        # If token expired, try to refresh (fallback for edge cases)
        if response.status_code == 401:
            logger.info("Access token expired (401 error), refreshing...")
            self.refresh_access_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            response = requests.get(url, headers=headers, params=params, timeout=30)

        response.raise_for_status()
        result = response.json()

        if result.get("status") != 0:
            raise ValueError(f"Withings API error: {result}")

        return result

    def get_weight_measurements(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, offset: int = 0
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
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now(timezone.utc)

        params = {
            "action": "getmeas",
            "meastype": 1,  # Weight
            "category": 1,  # Real measurements (not objectives)
            "startdate": int(start_date.timestamp()),
            "enddate": int(end_date.timestamp()),
            "offset": offset,
        }

        return self._make_authenticated_request("/measure", params)

    def get_all_weight_measurements(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
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
            response = self.get_weight_measurements(start_date=start_date, end_date=end_date, offset=offset)

            body = response.get("body", {})
            measuregrps = body.get("measuregrps", [])
            all_measurements.extend(measuregrps)

            # Check if there are more results
            more = body.get("more", 0)
            if more == 0:
                break

            offset += len(measuregrps)

        return all_measurements
