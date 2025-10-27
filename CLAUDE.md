# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Life Tracker is a Django-based personal data aggregation platform that syncs health and fitness data from multiple sources (Whoop, Withings, Toggl, Zero fasting app) into a unified database. The project follows a modular architecture where each data domain (workouts, weight, fasting, nutrition, time logs, goals, projects) is implemented as a separate Django app.

## Key Commands

### Development Server
```bash
python manage.py runserver
```

### Database Operations
```bash
# Run all migrations
python manage.py migrate

# Create new migration after model changes
python manage.py makemigrations

# Create superuser for Django admin
python manage.py createsuperuser
```

### Testing
```bash
# Run all tests
python manage.py test

# Run tests for specific app
python manage.py test workouts
python manage.py test weight
```

### Data Syncing Commands

The project uses custom management commands for data synchronization:

```bash
# Sync all data sources (master command)
python manage.py sync_all                # Last 30 days
python manage.py sync_all --days=90      # Custom range
python manage.py sync_all --whoop-only   # Only Whoop data

# Individual source syncing
python manage.py sync_whoop --days=30    # Whoop workouts
python manage.py sync_withings --days=30 # Withings weight data
python manage.py sync_toggl --days=30    # Toggl time entries
python manage.py import_zero             # Import Zero fasting data from CSV
```

### OAuth Authentication

OAuth credentials are stored in the `oauth_integration` app's database model. Initial setup requires running authentication commands:

```bash
# Authenticate with Whoop (opens browser for OAuth flow)
python manage.py whoop_auth

# Authenticate with Withings (opens browser for OAuth flow)
python manage.py withings_auth
```

## Architecture

### Centralized OAuth Management

All OAuth credentials are stored in `oauth_integration.models.OAuthCredential`. This model:
- Stores client IDs, secrets, and redirect URIs
- Manages access tokens and refresh tokens with expiration tracking
- Provides `update_tokens()` method for automatic token refresh persistence
- Each provider has a unique entry identified by the `provider` field ('whoop', 'withings')

API clients in `*/services/` directories load credentials from the database first, falling back to environment variables if database is unavailable (e.g., during initial setup).

### Django Apps Structure

Each data domain is a separate Django app:

- **workouts**: Exercise data from Whoop
  - Model: `Workout` (source, source_id, start, end, sport_id, heart rate, calories)
  - Service: `workouts/services/whoop_client.py` (WhoopAPIClient)

- **weight**: Weight measurements from Withings
  - Models: `WeighIn`, `OAuthCredential` (being phased out in favor of global oauth_integration)
  - Service: `weight/services/withings_client.py` (WithingsAPIClient)

- **fasting**: Fasting periods from Zero app
  - Model: `FastingPeriod` (start, end, duration)
  - Import via CSV: `python manage.py import_zero`

- **nutrition**: Food and meal tracking
  - Models: `Meal`, `FoodItem`

- **time_logs**: Time tracking from Toggl
  - Model: `TimeEntry` (project, description, start, end, duration)
  - Service: `time_logs/services/toggl_client.py` (TogglClient)

- **goals**: Goal setting and tracking
  - Model: `Goal`

- **projects**: Project management
  - Model: `Project`

### Service Layer Pattern

API integrations follow a consistent pattern with client classes in `<app>/services/`:
- Client initialization loads OAuth credentials from database or environment
- `get_authorization_url()`: Generate OAuth authorization URL
- `exchange_code_for_token()`: Exchange authorization code for tokens
- `refresh_access_token()`: Refresh expired tokens (automatically saves to database)
- Data fetching methods that handle authentication and API calls

### Data Models Pattern

All imported data models follow this pattern:
- `source`: String identifying data source (e.g., 'Whoop', 'Withings', 'Manual')
- `source_id`: Unique identifier from external system
- `unique_together = ['source', 'source_id']`: Prevents duplicates on re-sync
- Timestamps: `created_at`, `updated_at` for audit trails
- Indexes on timestamp fields for efficient querying

### Management Commands

Custom management commands are in `<app>/management/commands/`:
- `sync_all.py`: Master sync command in workouts app
- `whoop_auth.py`, `withings_auth.py`: OAuth authentication flows
- `sync_whoop.py`, `sync_withings.py`, `sync_toggl.py`: Individual data sync commands
- `import_zero.py`: CSV import for Zero fasting data
- `migrate_oauth_to_db.py`: Utility to migrate env var credentials to database

## Environment Configuration

The project uses `.env` for configuration (see `.env.example` for template):
- OAuth credentials (client IDs and secrets) can be in env vars or database
- OAuth tokens are automatically persisted to database after authentication
- API tokens for non-OAuth services (Toggl) remain in env vars
- Database URLs for production (PostgreSQL on Heroku)

## Important Implementation Notes

### OAuth Token Persistence
When implementing new OAuth integrations:
1. Store client credentials in `oauth_integration.OAuthCredential`
2. API clients should call `credential.update_tokens()` after token refresh
3. This prevents token expiration issues across sync runs

### Avoiding Duplicate Data
All sync commands use `update_or_create()` with `source` and `source_id` as lookup keys. This ensures:
- Re-running syncs doesn't create duplicates
- Data updates are captured if source system changes values
- Manual entries can coexist with API-synced data using different `source` values

### URL Routing
Main URL config in `lifetracker/urls.py` includes app URLs. Currently only fasting and nutrition have web views; other apps are data-only and accessible via Django admin at `/admin/`.

### Testing Approach
Test files exist but are minimal (`tests.py` in each app). When adding tests:
- Use Django's `TestCase` for database tests
- Mock external API calls using `unittest.mock` or similar
- Test OAuth token refresh logic separately from data sync logic

## Production Deployment

The project is configured for Heroku deployment:
- `Procfile`: Defines web dyno with Gunicorn
- `runtime.txt`: Specifies Python version
- WhiteNoise middleware: Serves static files
- Database: PostgreSQL in production, SQLite in development
- Environment variables set via Heroku config vars
