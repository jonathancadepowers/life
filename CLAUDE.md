# CLAUDE.md

## Project Overview

Life Tracker is a single-user Django app that aggregates personal data from external sources (Whoop, Withings, Toggl, Zero, Cronometer) into a unified database. Each data domain is a separate Django app. There is no user authentication — it's a personal tool.

## Key Commands

```bash
python manage.py runserver                # Dev server
python manage.py test                     # Run all tests
python manage.py test targets             # Run tests for one app
python manage.py migrate                  # Apply migrations
python manage.py makemigrations           # Generate migrations
python manage.py sync_all --days=30       # Sync Whoop, Withings, Cronometer
python manage.py sync_toggl --days=30     # Sync Toggl time entries
```

**IMPORTANT: After every change, ALWAYS push immediately to both GitHub and Heroku:**
```bash
git push origin main && git push heroku main
```

## Critical Invariants (Read These First)

### 1. Source + Source ID Deduplication
Every externally-synced model has `source` (CharField) and `source_id` (CharField) with `unique_together = ['source', 'source_id']`. Always use `update_or_create()` with BOTH fields as the lookup:
```python
Workout.objects.update_or_create(
    source='Whoop',           # Title-cased, not lowercase
    source_id=str(external_id),
    defaults={...}
)
```
Source values are **title-cased**: `'Whoop'`, `'Withings'`, `'Manual'`, `'Zero'`, `'Toggl'`, `'Cronometer'`. Manual entries use UUID for `source_id`.

### 2. Timezone Handling
- **Database stores UTC** (`USE_TZ = True`, `TIME_ZONE = 'UTC'`)
- **User timezone comes from a browser cookie**, not the database:
  ```python
  from targets.views import get_user_timezone, get_user_today
  user_tz = get_user_timezone(request)        # reads request.COOKIES['user_timezone']
  today, day_start, day_end = get_user_today(request)  # timezone-aware day boundaries
  ```
- Fallback is `'UTC'` if cookie is missing
- Frontend sends ISO 8601 with `Z` suffix. Parse with: `datetime.fromisoformat(value.replace('Z', '+00:00'))`

### 3. OAuth Token Persistence
All OAuth credentials live in `oauth_integration.models.OAuthCredential` (NOT `weight.models.OAuthCredential` — that's deprecated). After refreshing tokens, you MUST call:
```python
credential.update_tokens(access_token, refresh_token, expires_in)  # This calls .save()
```
API clients load credentials from the database first, falling back to env vars during initial setup.

### 4. AJAX View Response Format
All AJAX endpoints return this structure:
```python
return JsonResponse({'success': True, 'data': {...}})           # 200
return JsonResponse({'success': False, 'error': 'msg'}, status=400)  # Error
```

### 5. Sync Command Output Format
The frontend parses sync command output by searching for `SYNC SUMMARY` string. If you change the output format of any sync command, `fasting/views.py:master_sync()` will break.

## How To: Add a New Data Source

1. **Create the Django app:**
   ```bash
   python manage.py startapp mydata
   ```

2. **Define the model** with the standard fields:
   ```python
   class MyDataEntry(models.Model):
       source = models.CharField(max_length=50)
       source_id = models.CharField(max_length=255, db_index=True)
       # your data fields here (use DateTimeField for timestamps)
       created_at = models.DateTimeField(auto_now_add=True)
       updated_at = models.DateTimeField(auto_now=True)

       class Meta:
           unique_together = ['source', 'source_id']
           indexes = [models.Index(fields=['source', 'source_id'])]
   ```

3. **Create the API client** in `mydata/services/client.py`:
   - For OAuth APIs: follow `workouts/services/whoop_client.py`
   - For token APIs: follow `time_logs/services/toggl_client.py`
   - For subprocess/CLI: follow `nutrition/services/cronometer_client.py`

4. **Create the sync command** in `mydata/management/commands/sync_mydata.py`:
   - Accept `--days` and `--all` arguments
   - Use `update_or_create(source='MySource', source_id=..., defaults={...})`
   - Print summary with `✓ Created: N` / `↻ Updated: N` / `⊘ Skipped: N`

5. **Register in admin** in `mydata/admin.py`:
   ```python
   @admin.register(MyDataEntry)
   class MyDataEntryAdmin(admin.ModelAdmin):
       list_display = ('source', 'source_id', 'created_at')
       list_filter = ('source',)
       search_fields = ('source_id',)
       readonly_fields = ('created_at', 'updated_at')
   ```

6. **Add to INSTALLED_APPS** in `lifetracker/settings.py`

7. **Run migrations:** `python manage.py makemigrations mydata && python manage.py migrate`

## How To: Add an AJAX Endpoint

```python
# In myapp/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

@require_POST
def my_endpoint(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    # Do work here...
    return JsonResponse({'success': True, 'data': result})
```

Wire it up in `lifetracker/urls.py`:
```python
path('myapp/api/action/', myapp_views.my_endpoint, name='my_action'),
```

## Apps & Models Reference

| App | Models | External Source | Has Web UI |
|-----|--------|----------------|------------|
| `workouts` | `Workout` | Whoop | No (admin only) |
| `weight` | `WeighIn` | Withings | No (admin only) |
| `fasting` | `FastingSession` | Zero CSV / Manual | Yes (`/activity-logger/`) |
| `nutrition` | `NutritionEntry` | Cronometer | Yes (via activity logger) |
| `time_logs` | `TimeLog` | Toggl | No (admin only) |
| `goals` | `Goal` | Toggl tags | No (admin only) |
| `projects` | `Project` | Toggl projects | No (admin only) |
| `targets` | `DailyAgenda` | Manual | Yes (`/life-tracker/`, `/activity-report/`) |
| `todos` | `Task`, `TaskState`, `TaskTag`, `TaskSchedule`, `TimeBlock`, `TaskDetailTemplate`, `TaskView` | Manual | Yes (`/tasks/`) |
| `calendar_events` | `CalendarEvent` | Outlook/Gmail | Yes (embedded in task list) |
| `monthly_objectives` | `MonthlyObjective` | Manual | Yes (in activity report) |
| `settings` | `LifeTrackerColumn`, `Setting` | Manual | Yes (`/settings/`) |
| `inspirations_app` | `Inspiration` | Manual/Import | Yes (`/`) |
| `writing` | `BookCover`, `WritingPageImage`, `WritingLog` | Manual | Yes (`/writing/`) |
| `youtube_avoidance` | `YouTubeAvoidanceLog` | Manual | No |
| `waist_measurements` | `WaistCircumferenceMeasurement` | Manual | No |
| `oauth_integration` | `OAuthCredential`, `APICredential` | — | No (admin only) |
| `external_data` | `WhoopSportId` | Reference data | No |

### Models with non-standard primary keys
`Goal` and `Project` use external IDs as primary keys (not auto-increment). You must specify the ID when creating:
```python
Goal.objects.create(goal_id='12345', display_string='My Goal')
```

### Singleton model
`BookCover` uses `get_or_create(pk=1)` — only one instance exists.

### Configuration store
`Setting.get('key', 'default')` reads from a key-value table in the database.

## Architecture Notes

### Service Layer (`*/services/`)
API clients in `workouts/services/whoop_client.py`, `weight/services/withings_client.py`, `time_logs/services/toggl_client.py`, `nutrition/services/cronometer_client.py`. All load credentials from `oauth_integration` models first, then fall back to env vars.

### Templates
Each page is standalone (no shared base template). Templates use Bootstrap 5.3.0 and have their own `<style>` blocks. CSS classes are defined per-template, not in a shared stylesheet.

### Database
- **Development:** SQLite
- **Production:** PostgreSQL on Heroku (via `DATABASE_URL`)
- **Media storage:** Cloudinary in production, local filesystem in dev

### Sync Architecture
`sync_all` command orchestrates Whoop, Withings, and Cronometer syncs. Toggl and fasting are synced separately. The activity logger page (`/activity-logger/`) has a "Sync" button that calls `sync_all` via `fasting/views.py:master_sync()` and parses the command output.

## Common Mistakes to Avoid

1. **Don't import from `weight.models.OAuthCredential`** — use `oauth_integration.models.OAuthCredential`
2. **Don't use `update_or_create` with only `source_id`** — must include both `source` AND `source_id`
3. **Don't assume the server timezone matches the user's timezone** — always read from the cookie
4. **Don't use lowercase source names** — `'Whoop'` not `'whoop'`
5. **Don't change sync command output format** — the frontend parses it with string matching
6. **Don't forget `credential.update_tokens()` after OAuth token refresh** — tokens won't persist
7. **Don't create `Goal` or `Project` without specifying the ID** — they use custom primary keys
8. **Don't add `null=True` to CharField/TextField** — use `blank=True, default=''` instead (Django convention)

## Testing

Tests use Django's `TestCase` framework (no pytest). Key test patterns:
```bash
python manage.py test                          # All tests
python manage.py test workouts                 # One app
python manage.py test targets.tests.ClassName  # One class
```

See `tests/test_patterns.py` for executable examples of the deduplication, timezone, and response format patterns. When adding tests, mock external API calls — never make real HTTP requests.
