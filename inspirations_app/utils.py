from youtubesearchpython import VideosSearch


def get_youtube_trailer_url(film_title):
    """
    Search YouTube for a film trailer and return the URL.

    Args:
        film_title (str): Title of the film

    Returns:
        str: YouTube URL or None if not found
    """
    try:
        # Search for "{title} official trailer"
        search_query = f"{film_title} official trailer"
        videos_search = VideosSearch(search_query, limit=1)
        result = videos_search.result()

        if result and 'result' in result and len(result['result']) > 0:
            return result['result'][0]['link']

        return None
    except Exception as e:
        print(f"Error searching YouTube for {film_title}: {str(e)}")
        return None
