# Cronometer Integration

This document describes the Cronometer nutrition data integration for the Life Tracker app.

## Overview

The Cronometer integration automatically syncs your daily nutrition data (calories, fat, carbs, protein) from Cronometer.com into the Life Tracker database. It creates one `NutritionEntry` record per day with aggregated totals.

## Architecture

The integration consists of three components:

1. **Go CLI Tool** (`nutrition/cronometer_cli/`) - A standalone binary that uses the [gocronometer](https://github.com/jrmycanady/gocronometer) library to export data from Cronometer and output JSON
2. **Python Client** (`nutrition/services/cronometer_client.py`) - Python wrapper that calls the Go CLI and parses results
3. **Django Management Command** (`nutrition/management/commands/sync_cronometer.py`) - Django command that syncs data to the database

## Setup Instructions

### 1. Build the Go CLI

The Go CLI must be compiled before the integration will work:

```bash
cd nutrition/cronometer_cli
go mod download
go build -o cronometer_export
```

This creates the `cronometer_export` binary that the Python code calls.

### 2. Configure Environment Variables

Add your Cronometer credentials to your `.env` file:

```bash
CRONOMETER_USERNAME=your-email@example.com
CRONOMETER_PASSWORD=your-password
```

**Security Note**: These credentials are stored in environment variables. For production (Heroku), set these using `heroku config:set`.

### 3. Test the Integration

Test the standalone CLI:

```bash
cd nutrition/cronometer_cli
./cronometer_export \
  -username "your-email@example.com" \
  -password "your-password" \
  -start "2024-01-01" \
  -end "2024-01-31"
```

Test the Django management command:

```bash
python manage.py sync_cronometer --days=7
```

## Usage

### Manual Sync

Sync the last 30 days (default):
```bash
python manage.py sync_cronometer
```

Sync a specific number of days:
```bash
python manage.py sync_cronometer --days=90
```

### Automated Sync

The Cronometer sync is automatically included in the master sync command:

```bash
python manage.py sync_all --days=30
```

This is also triggered by the "Run Master Sync" button in the web UI.

## Data Model

Each day's nutrition data is stored as a single `NutritionEntry`:

- **source**: `"Cronometer"`
- **source_id**: The date in `YYYY-MM-DD` format (used for deduplication)
- **consumption_date**: The date at midnight in your local timezone
- **calories**: Total calories for the day
- **fat**: Total fat in grams
- **carbs**: Total carbohydrates in grams
- **protein**: Total protein in grams

Days with no nutrition data logged are skipped.

## Heroku Deployment

### Building the Go Binary on Heroku

Heroku doesn't have Go installed by default, so you need to build the binary locally and commit it:

```bash
# On your local machine with Go installed:
cd nutrition/cronometer_cli
go build -o cronometer_export
git add cronometer_export
git commit -m "Add Cronometer CLI binary"
git push heroku main
```

Alternatively, you can use Heroku's Go buildpack as a secondary buildpack, but this is more complex.

### Setting Credentials on Heroku

```bash
heroku config:set CRONOMETER_USERNAME=your-email@example.com -a jp-life
heroku config:set CRONOMETER_PASSWORD=your-password -a jp-life
```

## Troubleshooting

### "cronometer_export binary not found"

Build the Go CLI:
```bash
cd nutrition/cronometer_cli
go mod download
go build -o cronometer_export
```

### "Missing Cronometer credentials"

Set the environment variables:
```bash
export CRONOMETER_USERNAME=your-email@example.com
export CRONOMETER_PASSWORD=your-password
```

Or add them to your `.env` file.

### Authentication Errors

- Verify your Cronometer username (email) and password are correct
- Try logging in to cronometer.com in a browser to verify credentials
- Note: If you use social login (Google, etc.) for Cronometer, you may need to set a password in your account settings first

### No Data Returned

- Verify you have nutrition data logged in Cronometer for the date range
- Check that the dates in the export match your expectations
- Run the CLI manually with verbose output to debug

## Important Notes

1. **Personal Use Only**: The gocronometer library is intended for personal data backup only, not enterprise use. This complies with Cronometer's terms of service for personal accounts.

2. **Daily Aggregates**: This integration creates one entry per day with totals, not individual meal entries.

3. **Deduplication**: Re-running the sync for the same dates will update existing entries (using `source='Cronometer'` and `source_id=date` as the unique key).

4. **Timezone**: Dates are localized to America/Los_Angeles timezone. Update `sync_cronometer.py` if you need a different timezone.

## Future Enhancements

Potential improvements:
- Support for individual meal-level data (breakfast, lunch, dinner)
- Additional nutrient tracking (vitamins, minerals, etc.)
- Configurable timezone per user
- OAuth integration if Cronometer adds official API support
