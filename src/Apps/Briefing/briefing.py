import requests
import feedparser

# Agra, India Coordinates
LAT = 27.1767
LON = 78.0081

def get_weather():
    """
    Fetches current weather from Open-Meteo (No API Key required).
    """
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current_weather=true"
        response = requests.get(url)
        data = response.json()
        
        if 'current_weather' in data:
            cw = data['current_weather']
            return {
                "temp": cw['temperature'],
                "code": cw['weathercode'], # WMO code (0=Clear, 1-3=Cloudy, etc.)
                "wind": cw['windspeed']
            }
        return None
    except Exception as e:
        print(f"⚠️ Weather Error: {e}")
        return None

def get_tech_news():
    """
    Fetches top tech news from Google News RSS.
    """
    try:
        # RSS Feed for Technology (India Edition)
        rss_url = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?ceid=IN:en&hl=en-IN&gl=IN"
        feed = feedparser.parse(rss_url)
        
        headlines = []
        for entry in feed.entries[:3]: # Get top 3
            headlines.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.published
            })
        return headlines
    except Exception as e:
        print(f"⚠️ News Error: {e}")
        return []

def get_briefing_data():
    return {
        "weather": get_weather(),
        "news": get_tech_news()
    }