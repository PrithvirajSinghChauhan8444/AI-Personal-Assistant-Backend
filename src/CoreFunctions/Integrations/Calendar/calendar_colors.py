COLOR_NAME_TO_ID = {
    "lavender": "1",
    "sage": "2",
    "light green": "2",
    "grape": "3",
    "purple": "3",
    "violet": "3",
    "flamingo": "4",
    "pink": "4",
    "coral": "4",
    "salmon": "4",
    "banana": "5",
    "yellow": "5",
    "tangerine": "6",
    "orange": "6",
    "peacock": "7",
    "cyan": "7",
    "light blue": "7",
    "turquoise": "7",
    "graphite": "8",
    "gray": "8",
    "grey": "8",
    "blueberry": "9",
    "blue": "9",
    "dark blue": "9",
    "basil": "10",
    "green": "10",
    "dark green": "10",
    "tomato": "11",
    "red": "11",
}

def resolve_calendar_color_id(color: str = "orange") -> str:
    """
    Maps color name (e.g. 'orange', 'blue', 'green') or numeric ID string ('1'-'11')
    to Google Calendar's colorId string.
    Defaults to '6' (orange / tangerine).
    """
    if not color:
        return "6"
    
    color_clean = str(color).strip().lower()
    if color_clean in COLOR_NAME_TO_ID:
        return COLOR_NAME_TO_ID[color_clean]
    
    if color_clean in [str(i) for i in range(1, 12)]:
        return color_clean
        
    return "6"
