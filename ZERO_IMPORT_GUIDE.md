# Zero Fasting Data Import Guide

This guide explains how to import your fasting data from the Zero Fasting app into the Life Tracker database.

## Overview

Unlike Whoop and Withings which use API integrations, Zero Fasting doesn't provide an API. Instead, you can export your data as JSON files and import them manually.

## Data Export from Zero App

1. Open the Zero Fasting app on your phone
2. Go to Settings → Export Data
3. Export your data (you'll receive 8 JSON files)
4. The fasting session data is located in `biodata.json` under the `fast_data` key

## Data Structure

Each fasting session in Zero's export contains:
- **FastID**: Unique identifier (UUID)
- **StartDTM**: Start datetime (ISO 8601 format)
- **EndDTM**: End datetime (ISO 8601 format) - null for incomplete fasts
- **GoalHours**: Target fasting duration in hours
- **GoalID**: Fasting goal identifier (e.g., "twenty-intermittent", "circadian-rhythm")
- **IsEnded**: Boolean indicating if the fast was completed

## Setup Instructions

### 1. Create Database Tables

Run Django migrations to create the fasting tables:

```bash
python manage.py makemigrations fasting
python manage.py migrate
```

### 2. Import Your Zero Data

Use the import command to load your fasting data:

```bash
# Import from biodata.json
python manage.py import_zero import/temp/zero_data/zero-fasting-data_*/biodata.json

# Or specify the full path
python manage.py import_zero /path/to/biodata.json
```

### 3. Preview Before Importing (Optional)

You can do a dry-run to see what would be imported without actually importing:

```bash
python manage.py import_zero import/temp/zero_data/zero-fasting-data_*/biodata.json --dry-run
```

This will show you:
- How many fasting sessions would be created
- How many would be updated (if you're re-importing)
- Preview of each session

### 4. Verify Import

Check your data in the Django admin:

```bash
python manage.py runserver
```

Then visit http://127.0.0.1:8000/admin/ and navigate to "Fasting Sessions"

## Import Command Options

```bash
python manage.py import_zero <path_to_biodata.json> [options]

Options:
  --dry-run    Preview import without saving to database
```

## Features

The fasting app includes:

- **Django Model**: `FastingSession` with all fasting data
- **Admin Interface**: View and manage fasting sessions in Django admin
- **Duplicate Prevention**: Re-importing the same data won't create duplicates (uses `source_id` to identify unique fasts)
- **Calculated Fields**:
  - `duration` - Automatically calculated from start and end times
  - `duration_hours` - Duration in hours for easy analysis

## Re-importing Data

If you export new data from Zero in the future, you can safely re-import it:

```bash
python manage.py import_zero /path/to/new/biodata.json
```

The import command will:
- Create new fasting sessions that don't exist
- Update existing sessions if they've changed
- Skip duplicates

## Database Model

The `FastingSession` model stores:

| Field | Type | Description |
|-------|------|-------------|
| source | CharField | Data source (always "Zero" for imports) |
| source_id | CharField | FastID from Zero export |
| start | DateTimeField | Fast start time |
| end | DateTimeField | Fast end time (null for incomplete) |
| goal_hours | DecimalField | Target duration in hours |
| goal_id | CharField | Goal type identifier |
| is_ended | BooleanField | Whether fast was completed |
| created_at | DateTimeField | When record was created in DB |
| updated_at | DateTimeField | When record was last updated |

## Future Enhancements

Potential future additions:
- Automatic import from exported files in a watched directory
- Statistics and analytics views
- Integration with other health data (weight, workouts)
- Custom fasting goals and tracking
