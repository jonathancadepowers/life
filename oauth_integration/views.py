"""
OAuth integration views for handling authentication flows.

These views handle the OAuth 2.0 authorization flow for external services
like Whoop, Withings, etc.
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
import secrets

_REDIRECT_URL = 'fasting:activity_logger'


@require_http_methods(["GET"])
def whoop_authorize(request):
    """
    Initiate Whoop OAuth flow.

    Generates authorization URL and redirects user to Whoop for authentication.
    """
    try:
        from workouts.services.whoop_client import WhoopAPIClient

        client = WhoopAPIClient()

        # Generate state parameter for security
        state = secrets.token_urlsafe(32)
        request.session['whoop_oauth_state'] = state

        # Get authorization URL
        auth_url = client.get_authorization_url(state=state)

        return redirect(auth_url)

    except Exception as e:
        messages.error(request, f'Failed to initiate Whoop authentication: {e}')
        return redirect(_REDIRECT_URL)


@require_http_methods(["GET"])
def whoop_callback(request):
    """
    Handle Whoop OAuth callback.

    Exchanges authorization code for access tokens and saves to database.
    """
    try:
        from workouts.services.whoop_client import WhoopAPIClient

        # Get authorization code from callback
        code = request.GET.get('code')
        state = request.GET.get('state')

        if not code:
            error = request.GET.get('error', 'Unknown error')
            messages.error(request, f'Whoop authentication failed: {error}')
            return redirect(_REDIRECT_URL)

        # Verify state parameter (CSRF protection)
        expected_state = request.session.get('whoop_oauth_state')
        if state != expected_state:
            messages.error(request, 'Invalid state parameter. Please try again.')
            return redirect(_REDIRECT_URL)

        # Exchange code for tokens
        client = WhoopAPIClient()
        client.exchange_code_for_token(code)

        # Save tokens (already handled by client)
        messages.success(
            request,
            '✓ Successfully authenticated with Whoop! Your workouts will now sync automatically.'
        )

        # Clean up session
        if 'whoop_oauth_state' in request.session:
            del request.session['whoop_oauth_state']

        return redirect(_REDIRECT_URL)

    except ValueError as e:
        # Specific handling for token exchange errors
        messages.error(request, f'Whoop authentication error: {str(e)}')
        return redirect(_REDIRECT_URL)
    except Exception as e:
        # General error handling
        messages.error(request, f'Failed to complete Whoop authentication: {str(e)}')
        import traceback
        print(f'OAuth callback error: {traceback.format_exc()}')
        return redirect(_REDIRECT_URL)


@require_http_methods(["GET"])
def withings_authorize(request):
    """
    Initiate Withings OAuth flow.

    Generates authorization URL and redirects user to Withings for authentication.
    """
    try:
        from weight.services.withings_client import WithingsAPIClient

        client = WithingsAPIClient()

        # Generate state parameter for security (Withings requires min 8 chars)
        state = secrets.token_urlsafe(32)
        request.session['withings_oauth_state'] = state

        # Get authorization URL
        auth_url = client.get_authorization_url(state=state)

        return redirect(auth_url)

    except Exception as e:
        messages.error(request, f'Failed to initiate Withings authentication: {e}')
        return redirect(_REDIRECT_URL)


@require_http_methods(["GET"])
def withings_callback(request):
    """
    Handle Withings OAuth callback.

    Exchanges authorization code for access tokens and saves to database.
    """
    try:
        from weight.services.withings_client import WithingsAPIClient

        # Get authorization code from callback
        code = request.GET.get('code')
        state = request.GET.get('state')

        if not code:
            error = request.GET.get('error', 'Unknown error')
            messages.error(request, f'Withings authentication failed: {error}')
            return redirect(_REDIRECT_URL)

        # Verify state parameter (CSRF protection)
        expected_state = request.session.get('withings_oauth_state')
        if state != expected_state:
            messages.error(request, 'Invalid state parameter. Please try again.')
            return redirect(_REDIRECT_URL)

        # Exchange code for tokens
        client = WithingsAPIClient()
        client.exchange_code_for_token(code)

        # Save tokens (already handled by client)
        messages.success(
            request,
            '✓ Successfully authenticated with Withings! Your weight data will now sync automatically.'
        )

        # Clean up session
        if 'withings_oauth_state' in request.session:
            del request.session['withings_oauth_state']

        return redirect(_REDIRECT_URL)

    except ValueError as e:
        # Specific handling for token exchange errors
        messages.error(request, f'Withings authentication error: {str(e)}')
        return redirect(_REDIRECT_URL)
    except Exception as e:
        # General error handling
        messages.error(request, f'Failed to complete Withings authentication: {str(e)}')
        import traceback
        print(f'OAuth callback error: {traceback.format_exc()}')
        return redirect(_REDIRECT_URL)
