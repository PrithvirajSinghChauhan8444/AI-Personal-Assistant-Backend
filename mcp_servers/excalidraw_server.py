"""Local Excalidraw MCP Server for generating visual diagrams, flowcharts, and architecture maps."""

import json
import os
import random
from typing import Any, Dict, List

from base import SimpleMCPServer

ARTIFACTS_DIR = os.path.abspath("workspace/artifacts")

COLOR_PALETTES = {
    "blue": {"bg": "#d0ebff", "stroke": "#1971c2"},
    "green": {"bg": "#d3f9d8", "stroke": "#2f9e44"},
    "orange": {"bg": "#ffe8cc", "stroke": "#d9480f"},
    "red": {"bg": "#ffe3e3", "stroke": "#e03131"},
    "purple": {"bg": "#f3d9fa", "stroke": "#9c36b5"},
    "yellow": {"bg": "#fff3bf", "stroke": "#f08c00"},
    "gray": {"bg": "#f1f3f5", "stroke": "#495057"},
}


def sanitize_filename(name: str) -> str:
    """Removes invalid filename characters and appends .excalidraw extension."""
    clean = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name.strip())
    if not clean.endswith(".excalidraw"):
        clean += ".excalidraw"
    return clean


def make_shape_element(
    elem_id: str,
    elem_type: str,
    x: float,
    y: float,
    width: float,
    height: float,
    color_name: str = "blue",
) -> Dict[str, Any]:
    """Constructs an individual Excalidraw shape (rectangle, ellipse, diamond)."""
    palette = COLOR_PALETTES.get(color_name.lower(), COLOR_PALETTES["blue"])
    return {
        "id": elem_id,
        "type": elem_type,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": palette["stroke"],
        "backgroundColor": palette["bg"],
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "roundness": {"type": 3} if elem_type == "rectangle" else None,
        "seed": random.randint(10000, 99999),
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": [],
        "updated": 1,
        "link": None,
        "locked": False,
    }


def make_text_element(
    text_id: str,
    text: str,
    x: float,
    y: float,
    container_id: str = None,
    font_size: int = 16,
) -> Dict[str, Any]:
    """Constructs an Excalidraw text element centered inside a container."""
    approx_w = max(len(text) * 9, 40)
    approx_h = 24
    return {
        "id": text_id,
        "type": "text",
        "x": x,
        "y": y,
        "width": approx_w,
        "height": approx_h,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "roundness": None,
        "seed": random.randint(10000, 99999),
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1,
        "link": None,
        "locked": False,
        "text": text,
        "fontSize": font_size,
        "fontFamily": 1,
        "textAlign": "center",
        "verticalAlign": "middle",
        "containerId": container_id,
        "originalText": text,
    }


def make_arrow_element(
    arrow_id: str,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    from_id: str = None,
    to_id: str = None,
) -> Dict[str, Any]:
    """Constructs a connecting arrow with directional points."""
    dx = end_x - start_x
    dy = end_y - start_y
    return {
        "id": arrow_id,
        "type": "arrow",
        "x": start_x,
        "y": start_y,
        "width": abs(dx),
        "height": abs(dy),
        "angle": 0,
        "strokeColor": "#495057",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "roundness": {"type": 2},
        "seed": random.randint(10000, 99999),
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1,
        "link": None,
        "locked": False,
        "points": [[0, 0], [dx, dy]],
        "lastCommittedPoint": None,
        "startBinding": {"elementId": from_id, "focus": 0.1, "gap": 5} if from_id else None,
        "endBinding": {"elementId": to_id, "focus": -0.1, "gap": 5} if to_id else None,
        "startArrowhead": None,
        "endArrowhead": "arrow",
    }


def handle_create_diagram(args: Dict[str, Any]) -> str:
    """Generates an Excalidraw architectural diagram with nodes, labels, and arrows."""
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    name = sanitize_filename(args.get("name", "architecture_diagram"))
    title = args.get("title", "Architecture Diagram")
    nodes = args.get("nodes", [])
    connections = args.get("connections", [])

    elements = []
    # Add title at top
    title_elem = make_text_element("title_0", title, 100, 40, font_size=24)
    elements.append(title_elem)

    node_positions = {}
    cols = 3
    node_w = 180
    node_h = 70
    gap_x = 70
    gap_y = 90
    start_x = 100
    start_y = 110

    # Place nodes in a clean multi-row layout
    for idx, node in enumerate(nodes):
        node_id = str(node.get("id", f"node_{idx}"))
        label = node.get("label", node_id)
        shape_type = node.get("type", "rectangle")
        if shape_type not in ("rectangle", "ellipse", "diamond"):
            shape_type = "rectangle"
        color = node.get("color", "blue")

        row = idx // cols
        col = idx % cols
        x = start_x + col * (node_w + gap_x)
        y = start_y + row * (node_h + gap_y)

        node_positions[node_id] = {"x": x, "y": y, "w": node_w, "h": node_h}

        shape = make_shape_element(node_id, shape_type, x, y, node_w, node_h, color)
        text = make_text_element(f"txt_{node_id}", label, x + 15, y + 22, container_id=node_id)
        shape["boundElements"] = [{"type": "text", "id": f"txt_{node_id}"}]

        elements.extend([shape, text])

    # Connect nodes with arrows
    for idx, conn in enumerate(connections):
        from_id = str(conn.get("from_id", conn.get("from", "")))
        to_id = str(conn.get("to_id", conn.get("to", "")))

        if from_id in node_positions and to_id in node_positions:
            src = node_positions[from_id]
            dst = node_positions[to_id]

            # Bottom of source to top of destination, or right to left
            if dst["y"] > src["y"]:
                sx = src["x"] + src["w"] / 2
                sy = src["y"] + src["h"]
                dx = dst["x"] + dst["w"] / 2
                dy = dst["y"]
            else:
                sx = src["x"] + src["w"]
                sy = src["y"] + src["h"] / 2
                dx = dst["x"]
                dy = dst["y"] + dst["h"] / 2

            arrow_id = f"arrow_{idx}"
            arrow = make_arrow_element(arrow_id, sx, sy, dx, dy, from_id, to_id)
            elements.append(arrow)

    doc = {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {
            "gridSize": None,
            "viewBackgroundColor": "#ffffff",
        },
        "files": {},
    }

    file_path = os.path.join(ARTIFACTS_DIR, name)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)

    return (
        f"✅ Excalidraw diagram created successfully!\n\n"
        f"📁 File: {file_path}\n"
        f"📊 Elements: {len(elements)} items ({len(nodes)} nodes, {len(connections)} connections)\n\n"
        f"💡 How to view:\n"
        f"1. Open https://excalidraw.com in your browser.\n"
        f"2. Click the open folder icon (or press Ctrl+O) and choose {file_path}.\n"
        f"3. Or open it directly inside VS Code / Cursor with the Excalidraw extension."
    )


def handle_create_flowchart(args: Dict[str, Any]) -> str:
    """Generates a top-down visual flowchart from sequence steps and transitions."""
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    name = sanitize_filename(args.get("name", "flowchart"))
    title = args.get("title", "Process Flowchart")
    steps = args.get("steps", [])

    elements = []
    elements.append(make_text_element("title_fc", title, 150, 40, font_size=24))

    start_x = 180
    curr_y = 100
    node_w = 200
    node_h = 60
    gap_y = 65

    step_positions = {}
    for idx, s in enumerate(steps):
        s_id = str(s.get("id", f"step_{idx}"))
        label = s.get("text", s_id)
        s_type = s.get("type", "step")

        if s_type == "start" or s_type == "end":
            shape_type = "ellipse"
            color = "green" if s_type == "start" else "red"
        elif s_type == "decision":
            shape_type = "diamond"
            color = "yellow"
        else:
            shape_type = "rectangle"
            color = "blue"

        step_positions[s_id] = {"x": start_x, "y": curr_y, "w": node_w, "h": node_h}
        shape = make_shape_element(s_id, shape_type, start_x, curr_y, node_w, node_h, color)
        text = make_text_element(f"txt_{s_id}", label, start_x + 15, curr_y + 18, container_id=s_id)
        elements.extend([shape, text])

        if idx > 0:
            prev_id = steps[idx - 1].get("id", f"step_{idx-1}")
            prev = step_positions[prev_id]
            arrow = make_arrow_element(
                f"arrow_fc_{idx}",
                prev["x"] + prev["w"] / 2,
                prev["y"] + prev["h"],
                start_x + node_w / 2,
                curr_y,
                from_id=prev_id,
                to_id=s_id,
            )
            elements.append(arrow)

        curr_y += node_h + gap_y

    doc = {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
        "files": {},
    }

    file_path = os.path.join(ARTIFACTS_DIR, name)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)

    return (
        f"✅ Flowchart created successfully!\n\n"
        f"📁 File: {file_path}\n"
        f"📊 Steps: {len(steps)}\n\n"
        f"💡 How to view:\n"
        f"Drop {file_path} into https://excalidraw.com to view or edit visually."
    )


def handle_list_diagrams(args: Dict[str, Any]) -> str:
    """Lists all created Excalidraw diagrams in workspace/artifacts/."""
    if not os.path.isdir(ARTIFACTS_DIR):
        return "No diagrams directory found yet."

    files = [f for f in os.listdir(ARTIFACTS_DIR) if f.endswith(".excalidraw")]
    if not files:
        return "No Excalidraw diagram files found in workspace/artifacts/."

    lines = ["Available Excalidraw Diagrams:"]
    for f in sorted(files):
        p = os.path.join(ARTIFACTS_DIR, f)
        size_kb = os.path.getsize(p) / 1024
        lines.append(f"- {f} ({size_kb:.1f} KB) -> {p}")

    return "\n".join(lines)


def main():
    server = SimpleMCPServer("excalidraw-mcp", "1.0.0")

    server.register_tool(
        name="create_diagram",
        description="Creates an Excalidraw architecture diagram or visual map with colored nodes, shapes, and arrows, saving to workspace/artifacts/.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Base filename for the diagram (e.g. system_architecture)"},
                "title": {"type": "string", "description": "Title text displayed at the top of the canvas"},
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "type": {"type": "string", "enum": ["rectangle", "ellipse", "diamond"], "default": "rectangle"},
                            "color": {"type": "string", "enum": ["blue", "green", "orange", "red", "purple", "yellow", "gray"], "default": "blue"},
                        },
                        "required": ["id", "label"],
                    },
                    "description": "List of boxes/shapes to place on the canvas",
                },
                "connections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from_id": {"type": "string"},
                            "to_id": {"type": "string"},
                            "label": {"type": "string"},
                        },
                        "required": ["from_id", "to_id"],
                    },
                    "description": "Directed arrows connecting from_id to to_id",
                },
            },
            "required": ["name", "nodes"],
        },
        handler=handle_create_diagram,
    )

    server.register_tool(
        name="create_flowchart",
        description="Creates a top-down visual flowchart from sequential steps (start, step, decision, end).",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Filename without extension (e.g. login_flow)"},
                "title": {"type": "string", "description": "Flowchart title header"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "text": {"type": "string"},
                            "type": {"type": "string", "enum": ["start", "step", "decision", "end"], "default": "step"},
                        },
                        "required": ["id", "text"],
                    },
                    "description": "Sequential steps of the process",
                },
            },
            "required": ["name", "steps"],
        },
        handler=handle_create_flowchart,
    )

    server.register_tool(
        name="list_diagrams",
        description="Lists all saved Excalidraw diagram files in workspace/artifacts/.",
        input_schema={"type": "object"},
        handler=handle_list_diagrams,
    )

    server.run()


if __name__ == "__main__":
    main()
