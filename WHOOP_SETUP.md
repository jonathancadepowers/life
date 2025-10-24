# Whoop API Integration Setup Guide

This guide will help you set up the Whoop API integration to automatically sync your workout data into the Life Tracker app.

## Prerequisites

- A Whoop account with an active subscription
- Python environment with dependencies installed (`pip install -r requirements.txt`)

## Step 1: Register Your Application with Whoop

1. Go to the [Whoop Developer Portal](https://developer.whoop.com/)
2. Sign in with your Whoop account
3. Navigate to "Applications" and click "Create Application"
4. Fill in the application details:
   - **Application Name**: Life Tracker (or your preferred name)
   - **Description**: Personal life tracking application
   - **Redirect URI**: `http://localhost:8000/whoop/callback`
   - **Scopes**: Select all relevant scopes (read:profile, read:workout, read:cycles, read:recovery, read:sleep)
5. Save the application
6. Copy your **Client ID** and **Client Secret** (keep these secure!)

## Step 2: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file and add your Whoop credentials:
   ```bash
   # WHOOP API Configuration
   WHOOP_CLIENT_ID=your-client-id-here
   WHOOP_CLIENT_SECRET=your-client-secret-here
   WHOOP_REDIRECT_URI=http://localhost:8000/whoop/callback
   ```

## Step 3: Authenticate with Whoop

Run the authentication command to obtain your access and refresh tokens:

```bash
python manage.py whoop_auth
```

This command will:
1. Generate an authorization URL
2. Open your browser to the Whoop authorization page
3. After you authorize, you'll be redirected with an authorization code
4. Paste the code back into the terminal
5. The command will exchange the code for access and refresh tokens

**Copy the tokens displayed and add them to your `.env` file:**
```bash
WHOOP_ACCESS_TOKEN=your-access-token-here
WHOOP_REFRESH_TOKEN=your-refresh-token-here
```

## Step 4: Sync Your Workouts

Now you can sync your workout data from Whoop:

### Sync last 30 days (default):
```bash
python manage.py sync_whoop
```

### Sync custom number of days:
```bash
python manage.py sync_whoop --days=90
```

### Sync all available workouts:
```bash
python manage.py sync_whoop --all
```

## Step 5: View Your Data

1. Start the Django development server:
   ```bash
   python manage.py runserver
   ```

2. Go to the Django Admin: http://127.0.0.1:8000/admin/

3. Navigate to the "Workouts" section to view your synced data

## Automatic Token Refresh

The Whoop client automatically refreshes your access token when it expires (every hour). The refresh token allows the app to get new access tokens without requiring you to re-authenticate.

If you get authentication errors, you may need to re-run `python manage.py whoop_auth` to obtain fresh tokens.

## Understanding Sport IDs

Whoop uses numeric sport IDs to categorize workouts. The app includes a comprehensive mapping in `workouts/sport_ids.py` that translates these IDs to human-readable sport names:

- 0: Running
- 1: Cycling
- 44: Yoga
- 45: Weightlifting
- 48: Functional Fitness
- And many more...

The Django admin will automatically display sport names instead of IDs.

## Data Synced

The following workout data is synced from Whoop:

- **Start/End Time**: When the workout occurred
- **Sport Type**: What type of activity (running, cycling, etc.)
- **Heart Rate**: Average and maximum heart rate during the workout
- **Calories**: Total calories burned (converted from kilojoules)
- **Timezone**: Timezone offset for the workout

## Troubleshooting

### "No module named 'django'" error
Make sure your virtual environment is activated:
```bash
source venv/bin/activate
```

### "Configuration error: WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET must be set"
Check that your `.env` file is in the project root directory and contains your credentials.

### "401 Unauthorized" error
Your access token may have expired. The client should automatically refresh it, but if not, re-run the authentication:
```bash
python manage.py whoop_auth
```

### Workout is skipped with "not yet scored"
Some workouts may not be scored immediately by Whoop. Wait a bit and re-run the sync command.

## API Rate Limits

Be mindful of Whoop's API rate limits. The sync command fetches data in pages of 25 workouts, which should be well within rate limits for personal use.

## Security Notes

- Never commit your `.env` file to version control
- Keep your Client Secret secure
- Refresh tokens allow long-term access, so protect them
- The `.gitignore` file is already configured to exclude `.env`

## Scheduling Automatic Syncs (Optional)

You can set up a cron job to automatically sync workouts daily:

```bash
# Add to crontab (crontab -e)
0 6 * * * cd /path/to/life && source venv/bin/activate && python manage.py sync_whoop --days=7
```

This runs the sync every day at 6 AM for the last 7 days of workouts.

## Next Steps

- Set up additional data sources (food tracking, weight, etc.)
- Build custom visualizations and reports
- Export data for analysis
- Set up webhooks for real-time sync (advanced)
