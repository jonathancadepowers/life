from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime, time
from .models import FastingSession
from lifetracker.timezone_utils import get_user_timezone
import uuid


def activity_logger(request):
    """Render the Activity Logger page.

    Note: We don't pass today's agenda in the context because we want
    JavaScript to determine "today" based on the user's browser timezone,
    not the server's timezone. JavaScript will fetch the agenda via AJAX
    on page load.
    """
    from projects.models import Project

    # Get all projects for the dropdowns
    projects = Project.objects.all().order_by("display_string")

    context = {
        "projects": projects,
        "agenda": None,  # JavaScript will fetch today's agenda based on user's timezone
    }

    return render(request, "fasting/activity_logger.html", context)


@require_http_methods(["POST"])
def log_fast(request):
    """
    AJAX endpoint to log a new fast.

    Expects POST data:
        - hours: integer (12, 16, or 18)
        - date: string (YYYY-MM-DD format) - the date for the fast

    Returns JSON:
        - success: boolean
        - message: string
        - fast_id: integer (if successful)
    """
    try:
        # Get the fast duration and date from POST data
        hours = request.POST.get("hours")
        date_str = request.POST.get("date")

        if not hours:
            return JsonResponse({"success": False, "message": "Fast duration is required"}, status=400)

        if not date_str:
            return JsonResponse({"success": False, "message": "Date is required"}, status=400)

        try:
            hours = int(hours)
        except ValueError:
            return JsonResponse({"success": False, "message": "Invalid fast duration"}, status=400)

        if hours not in [12, 16, 18]:
            return JsonResponse({"success": False, "message": "Fast duration must be 12, 16, or 18 hours"}, status=400)

        # Parse the date string
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"success": False, "message": "Invalid date format. Use YYYY-MM-DD"}, status=400)

        # Get user's timezone from cookie (set by browser)
        user_tz = get_user_timezone(request)

        # Fast ends at 12:00 PM (noon) on the selected date in user's timezone
        # Create a naive datetime at noon on the selected date
        fast_end_date_naive = datetime.combine(selected_date, time(12, 0))

        # Localize to user's timezone (this handles DST correctly)
        fast_end_date = user_tz.localize(fast_end_date_naive)

        # Generate a unique source_id for manual entries
        source_id = str(uuid.uuid4())

        fast = FastingSession.objects.create(
            source="Manual",
            source_id=source_id,
            duration=hours,
            fast_end_date=fast_end_date,  # This is now timezone-aware and will be stored as UTC in DB
        )

        return JsonResponse(
            {
                "success": True,
                "message": f'{hours}-hour fast logged successfully for {selected_date.strftime("%B %d, %Y")}!',
                "fast_id": fast.id,
                "duration": float(fast.duration),
                "fast_end_date": fast_end_date.strftime("%Y-%m-%d %H:%M"),
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "message": f"Error logging fast: {str(e)}"}, status=500)


@require_http_methods(["POST"])
def master_sync(_request):
    """
    AJAX endpoint to trigger the master sync command.

    Runs sync_all and uses structured SyncResult objects (not string parsing)
    to build the response.

    Returns JSON:
        - success: boolean
        - message: string (with count of new entries)
        - results: dict per source {success, created, updated, skipped, error}
        - auth_errors: dict of sources with auth failures
        - has_errors: boolean
    """
    try:
        from io import StringIO
        from workouts.management.commands.sync_all import Command as SyncAllCommand

        # Run sync_all and capture its structured results
        output = StringIO()
        cmd = SyncAllCommand()
        cmd.stdout = output
        cmd.stderr = StringIO()
        cmd.handle(days=30, whoop_only=False, verbosity=1)

        # Build response from structured SyncResult objects
        results = {}
        auth_errors = {}
        has_errors = False
        total_created = 0

        for source, result in cmd.sync_results.items():
            results[source] = {
                "success": result.success,
                "created": result.created,
                "updated": result.updated,
                "skipped": result.skipped,
                "summary": result.summary,
            }
            total_created += result.created
            if not result.success:
                has_errors = True
                results[source]["error"] = result.error_message
            if result.auth_error:
                auth_errors[source] = True

        message = f'Synced {total_created} new {"entry" if total_created == 1 else "entries"}!'

        return JsonResponse(
            {
                "success": True,
                "message": message,
                "results": results,
                "auth_errors": auth_errors,
                "has_errors": has_errors,
            }
        )

    except Exception as e:
        import traceback

        return JsonResponse(
            {"success": False, "message": f"Error running master sync: {str(e)}", "traceback": traceback.format_exc()},
            status=500,
        )
