import webbrowser
import urllib.parse

def search_google(query):
    """Search Google for a query."""
    try:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"Searching Google for: {query}"
    except Exception as e:
        return f"Error searching Google: {e}"

def open_url(url):
    """Open a specific URL."""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opening {url}"
    except Exception as e:
        return f"Error opening URL: {e}"
