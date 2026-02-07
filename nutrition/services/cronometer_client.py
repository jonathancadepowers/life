"""
Cronometer API Client

This module provides a Python interface to export nutrition data from Cronometer
using the Go CLI wrapper that uses the gocronometer library.
"""
import json
import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CronometerClient:
    """Client for exporting nutrition data from Cronometer."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the Cronometer client.

        Args:
            username: Cronometer username (email). If not provided, uses CRONOMETER_USERNAME env var.
            password: Cronometer password. If not provided, uses CRONOMETER_PASSWORD env var.
        """
        self.username = username or os.getenv('CRONOMETER_USERNAME')
        self.password = password or os.getenv('CRONOMETER_PASSWORD')

        if not self.username or not self.password:
            raise ValueError(
                "Cronometer credentials not provided. "
                "Set CRONOMETER_USERNAME and CRONOMETER_PASSWORD environment variables."
            )

        # Find the Go CLI binary
        self.cli_path = self._find_cli_binary()

    def _find_cli_binary(self) -> Path:
        """
        Find the cronometer_export CLI binary.

        Returns:
            Path to the CLI binary.

        Raises:
            FileNotFoundError: If the binary is not found.
        """
        # Check in the cronometer_cli directory
        base_dir = Path(__file__).parent.parent / 'cronometer_cli'
        binary_path = base_dir / 'cronometer_export'

        if binary_path.exists():
            return binary_path

        # Check if it's in PATH
        try:
            result = subprocess.run(['which', 'cronometer_export'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
        except Exception:
            logger.debug("Could not locate cronometer_export binary via 'which' command")

        raise FileNotFoundError(
            f"cronometer_export binary not found. "
            f"Please build it by running:\n"
            f"  cd {base_dir}\n"
            f"  go build -o cronometer_export"
        )

    def export_daily_nutrition(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Export daily nutrition data for a date range.

        Args:
            start_date: Start date for the export.
            end_date: End date for the export. Defaults to today.

        Returns:
            List of dictionaries containing daily nutrition data:
            [
                {
                    'date': '2024-01-15',
                    'calories': 1850.5,
                    'fat': 65.2,
                    'carbs': 180.3,
                    'protein': 120.1
                },
                ...
            ]

        Raises:
            subprocess.CalledProcessError: If the CLI command fails.
            json.JSONDecodeError: If the CLI output is not valid JSON.
        """
        if end_date is None:
            end_date = datetime.now()

        # Format dates as YYYY-MM-DD
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        # Call the Go CLI
        cmd = [
            str(self.cli_path),
            '-username', self.username,
            '-password', self.password,
            '-start', start_str,
            '-end', end_str
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60  # 60 second timeout
            )

            # Parse JSON output
            data = json.loads(result.stdout)
            return data

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise Exception(f"Failed to export Cronometer data: {error_msg}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Cronometer export data: {e}\nOutput: {result.stdout}")
        except subprocess.TimeoutExpired:
            raise Exception("Cronometer export timed out after 60 seconds")

    def get_daily_nutrition_for_days(self, days: int = 30) -> List[Dict]:
        """
        Get daily nutrition data for the last N days.

        Args:
            days: Number of days to retrieve (default: 30)

        Returns:
            List of daily nutrition dictionaries.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.export_daily_nutrition(start_date, end_date)
