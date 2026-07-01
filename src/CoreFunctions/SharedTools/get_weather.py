import requests
from langchain_core.tools import StructuredTool

def get_weather(location: str = "Agra") -> str:
    """Fetches current weather using wttr.in (No API key needed).

    Args:
        location (str): The name of the city to get the weather for. Defaults to "Agra".
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: get_weather")
    print(f"   Args: location={location}")
    try:
        url = f"https://wttr.in/{location}?format=%C+%t"
        response = requests.get(url)
        return f"Current weather in {location}: {response.text.strip()}"
    except Exception as e:
        return f"Error fetching weather: {e}"

get_weather_tool = StructuredTool.from_function(
    func=get_weather,
    name="get_weather",
    description="Fetches current weather using wttr.in (No API key needed)."
)
