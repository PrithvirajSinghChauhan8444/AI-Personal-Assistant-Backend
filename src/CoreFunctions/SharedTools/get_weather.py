import requests
from langchain_core.tools import StructuredTool

def get_weather(location: str = "Agra") -> str:
    """Fetches current weather using wttr.in (No API key needed).

    Args:
        location (str): The name of the city to get the weather for. Defaults to "Agra".
    """
    print(f"\033[90m🛠️  [Tool] get_weather(location={repr(location)})\033[0m", flush=True)
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
