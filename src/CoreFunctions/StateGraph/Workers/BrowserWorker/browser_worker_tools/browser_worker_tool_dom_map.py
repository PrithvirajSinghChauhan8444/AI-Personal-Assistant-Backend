from langchain_core.tools import StructuredTool
from typing import Optional
from .browser_manager import _get_browser_page, DOM_MAP_SCRIPT


async def browser_get_dom_map(
    offset: int = 0,
    limit: int = 30,
    filter_role: Optional[str] = None
) -> str:
    """Returns a spatial layout map of all interactive elements on the current page.

    Each entry shows the element's ID, semantic role, label, center coordinates (x, y),
    and bounding-box size (width × height). Use the ID with browser_click or browser_input.

    Args:
        offset (int): Starting index for pagination. Defaults to 0.
        limit (int): Maximum number of elements to return. Defaults to 30.
        filter_role (str, optional): Restrict results to a specific role.
            Valid values: 'button', 'textbox', 'link', 'select', 'checkbox', 'other'.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_get_dom_map")
    print(f"   Args: offset={offset}, limit={limit}, filter_role={filter_role}")

    VALID_ROLES = {"button", "textbox", "link", "select", "checkbox", "other"}
    if filter_role and filter_role not in VALID_ROLES:
        return (
            f"Error: Invalid filter_role '{filter_role}'. "
            f"Valid values are: {', '.join(sorted(VALID_ROLES))}"
        )

    try:
        page = await _get_browser_page()
        elements = await page.evaluate(DOM_MAP_SCRIPT)

        if not elements:
            return "No interactive elements found on this page."

        if filter_role:
            elements = [e for e in elements if e["role"] == filter_role]

        total = len(elements)
        paginated = elements[offset:offset + limit]

        if not paginated:
            return (
                f"No elements found in range [{offset}–{offset + limit}]. "
                f"(Total{' filtered' if filter_role else ''}: {total})"
            )

        lines = []
        for el in paginated:
            label_str = f'"{el["label"]}"' if el["label"] else "(no label)"
            lines.append(
                f'[{el["id"]}] {el["role"]} {label_str} '
                f'at ({el["x"]}, {el["y"]}) {el["width"]}×{el["height"]}'
            )

        header = (
            f"DOM map — showing {offset}–{offset + len(paginated) - 1} "
            f"of {total} elements"
            + (f" (role='{filter_role}')" if filter_role else "")
            + ". Use offset/limit to paginate.\n"
        )
        return header + "\n".join(lines)

    except Exception as e:
        return f"Error building DOM map: {e}"


async def browser_query_elements(
    query_text: str,
    max_results: int = 10
) -> str:
    """Fuzzy-searches the current page's DOM map for elements whose label contains query_text.

    Useful when you know what you're looking for (e.g. 'search', 'login', 'submit')
    instead of scrolling through the full DOM map.

    Args:
        query_text (str): The text to search for in element labels (case-insensitive).
        max_results (int): Maximum number of matching elements to return. Defaults to 10.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: browser_query_elements")
    print(f"   Args: query_text={query_text!r}, max_results={max_results}")

    if not query_text or not query_text.strip():
        return "Error: query_text cannot be empty."

    try:
        page = await _get_browser_page()
        elements = await page.evaluate(DOM_MAP_SCRIPT)

        if not elements:
            return "No interactive elements found on this page."

        needle = query_text.strip().lower()
        matches = [
            e for e in elements
            if needle in (e["label"] or "").lower()
        ]

        if not matches:
            return f"No elements found matching '{query_text}'."

        matches = matches[:max_results]
        lines = []
        for el in matches:
            label_str = f'"{el["label"]}"' if el["label"] else "(no label)"
            lines.append(
                f'[{el["id"]}] {el["role"]} {label_str} '
                f'at ({el["x"]}, {el["y"]}) {el["width"]}×{el["height"]}'
            )

        header = f"Found {len(matches)} element(s) matching '{query_text}':\n"
        return header + "\n".join(lines)

    except Exception as e:
        return f"Error querying elements: {e}"


browser_get_dom_map_tool = StructuredTool.from_function(
    func=browser_get_dom_map,
    name="browser_get_dom_map",
    coroutine=browser_get_dom_map,
    description=(
        "Get a spatial DOM map of the current page — shows each interactive element's "
        "role, label, coordinates (x, y), and size. The primary tool to 'see' the page. "
        "Supports offset/limit pagination and optional role filtering "
        "(button | textbox | link | select | checkbox | other)."
    )
)

browser_query_elements_tool = StructuredTool.from_function(
    func=browser_query_elements,
    name="browser_query_elements",
    coroutine=browser_query_elements,
    description=(
        "Fuzzy-search the current page's interactive elements by label text. "
        "Use when you know what you're looking for (e.g. 'search', 'login', 'submit') "
        "instead of scanning the full DOM map. Returns matching elements with their IDs."
    )
)
