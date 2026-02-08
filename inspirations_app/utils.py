from youtubesearchpython import VideosSearch
import requests


def validate_youtube_url(url):
    """
    Check if a YouTube URL is still available.

    Args:
        url (str): YouTube URL to validate

    Returns:
        bool: True if video is available, False otherwise
    """
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        # YouTube returns 200 for valid videos
        return response.status_code == 200
    except Exception:
        return False


def get_youtube_trailer_url(film_title):
    """
    Search YouTube for a film trailer and return a validated URL.

    Args:
        film_title (str): Title of the film

    Returns:
        str: YouTube URL or None if not found/unavailable
    """
    try:
        # Search for "{title} official trailer"
        search_query = f"{film_title} official trailer"
        videos_search = VideosSearch(search_query, limit=5)  # Get top 5 results
        result = videos_search.result()

        if result and "result" in result and len(result["result"]) > 0:
            # Try each result until we find a valid one
            for video in result["result"]:
                url = video["link"]
                if validate_youtube_url(url):
                    return url

        return None
    except Exception as e:
        print(f"Error searching YouTube for {film_title}: {str(e)}")
        return None
