import json
from datetime import datetime
from langchain_core.tools import StructuredTool

def get_time() -> str:
    """Returns the current system time.

    Returns:
        str: The formatted current system time string.
    """
    print(f"\033[90m🛠️  [Tool] get_time()\033[0m", flush=True)
    return datetime.now().strftime("%I:%M %p, %A %d %B %Y")

get_time_tool = StructuredTool.from_function(
    func=get_time,
    name="get_time",
    description="Returns the current system time."
)
