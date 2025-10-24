# Life Tracker

A personal data aggregation and visualization platform to track various aspects of daily life including exercise, weight, food consumption, and fasting.

## Features

- **Data Integration**: Connect with third-party APIs (Whoop, MyFitnessPal, etc.)
- **Personal Database**: Store all your health and fitness data in one place
- **Custom Reporting**: View and analyze your data with custom visualizations
- **Django Admin**: Built-in admin interface for data management

## Integrations

### Currently Available
- **Exercise tracking (Whoop API)** - Sync workout data including heart rate, calories, and activity types

### Planned
- Weight tracking
- Food consumption tracking
- Fasting tracking

## Tech Stack

- **Backend**: Django 4.2 LTS
- **Database**: SQLite (development), PostgreSQL (production)
- **Frontend**: Django Templates + Bootstrap 5
- **API Integration**: Whoop API v2
- **Task Queue**: Celery + Redis (for future scheduled syncs)
- **Visualization**: Chart.js / Plotly (planned)

## Setup Instructions

### Prerequisites

- Python 3.11+
- pip

### Installation

1. Clone the repository:
```bash
cd /Users/jonathanpowers/repos
git clone https://github.com/jonathancadepowers/life.git
cd life
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Mac/Linux
# or
venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create a superuser:
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

7. Visit http://127.0.0.1:8000/ in your browser

## Whoop Integration Setup

To sync your workout data from Whoop, follow the detailed setup guide:

**[Whoop API Integration Setup Guide](WHOOP_SETUP.md)**

Quick start:
1. Register your app at https://developer.whoop.com/
2. Add credentials to `.env` file
3. Run `python manage.py whoop_auth` to authenticate
4. Run `python manage.py sync_whoop` to sync workouts

## Syncing Data

### Master Sync Command

Use the `sync_all` command to sync data from all configured sources:

```bash
# Sync last 30 days from all sources
python manage.py sync_all

# Sync custom time range
python manage.py sync_all --days=90

# Only sync Whoop (skip other sources)
python manage.py sync_all --whoop-only
```

### Individual Source Sync

You can also sync individual data sources:

```bash
# Sync Whoop workouts only
python manage.py sync_whoop --days=30
```

### Scheduling Automatic Syncs

Set up a cron job to automatically sync daily:

```bash
# Edit crontab
crontab -e

# Add this line to sync daily at 6 AM
0 6 * * * cd /Users/jonathanpowers/Repos/life && source venv/bin/activate && python manage.py sync_all --days=7 >> /tmp/life-sync.log 2>&1
```

Or use macOS `launchd` for more reliable scheduling:

1. Create `~/Library/LaunchAgents/com.lifetracker.sync.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.lifetracker.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/jonathanpowers/Repos/life/venv/bin/python</string>
        <string>/Users/jonathanpowers/Repos/life/manage.py</string>
        <string>sync_all</string>
        <string>--days=7</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/jonathanpowers/Repos/life</string>
</dict>
</plist>
```

2. Load the job:
```bash
launchctl load ~/Library/LaunchAgents/com.lifetracker.sync.plist
```

## Development

### Project Structure

```
life/
├── lifetracker/        # Main Django project settings
├── workouts/           # Workout tracking app
│   ├── models.py       # Workout data model
│   ├── admin.py        # Django admin configuration
│   ├── services/       # API clients (Whoop, etc.)
│   └── management/     # Custom management commands
├── manage.py           # Django management script
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── WHOOP_SETUP.md     # Whoop integration guide
```

### Running Tests

```bash
python manage.py test
```

### Creating a New App

```bash
python manage.py startapp <app_name>
```

## Environment Variables

Create a `.env` file in the root directory with:

```
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3

# API Keys (to be added as integrations are built)
WHOOP_CLIENT_ID=
WHOOP_CLIENT_SECRET=
```

## Contributing

This is a personal project, but feel free to fork and adapt for your own use!

## License

MIT License
