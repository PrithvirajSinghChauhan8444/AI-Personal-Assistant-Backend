from .classroom_worker_tools import classroom_tools

def compile_tool_prompt_section(tools: list) -> str:
    sections = []
    for tool in tools:
        desc = tool.description.strip() if tool.description else "No description."
        args = tool.args if hasattr(tool, 'args') else {}
        param_str = ", ".join(args.keys()) if args else "none"
        sections.append(f"- `{tool.name}({param_str})`:\n  {desc}")
    return "\n\n".join(sections)

BASE_PROMPT = """You are ClassroomWorker. You manage Google Classroom courses, assignments, announcements, and coursework details."""

SYSTEM_PROMPT = BASE_PROMPT + "\n\nAvailable Tools and Syntax:\n" + compile_tool_prompt_section(classroom_tools)
