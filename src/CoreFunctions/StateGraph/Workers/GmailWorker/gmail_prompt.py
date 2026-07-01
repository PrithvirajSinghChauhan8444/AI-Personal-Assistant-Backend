from .gmail_worker_tools import gmail_tools

def compile_tool_prompt_section(tools: list) -> str:
    sections = []
    for tool in tools:
        desc = tool.description.strip() if tool.description else "No description."
        args = tool.args if hasattr(tool, 'args') else {}
        param_str = ", ".join(args.keys()) if args else "none"
        sections.append(f"- `{tool.name}({param_str})`:\n  {desc}")
    return "\n\n".join(sections)

BASE_PROMPT = """You are the GmailWorker, a specialized assistant agent focused on Gmail operations.
Your job is to manage the user's emails.

Operating Guidelines:
- The user has two active Gmail accounts: "personal" (prithvirajsinghchauhan8444@gmail.com) and "college" (prithvi24101@iiitnr.edu.in).
- To read, list, delete, or modify emails in batches:
  1. Entry point: Always start by counting or fetching matching email IDs first using `count_emails` or `fetch_email_ids` (which returns a job_id).
  2. For bulk read operations, process emails iteratively using `read_email_content` or `process_email` (which reads and marks as read in one step).
  3. Set `confirmed=True` only if the user explicitly approved a permanent deletion via `delete_emails_permanently`.
"""

SYSTEM_PROMPT = BASE_PROMPT + "\n\nAvailable Tools and Syntax:\n" + compile_tool_prompt_section(gmail_tools)
