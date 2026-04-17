from .base_agent import Agent, AgentConfig
from .orchestrator import AgentManager

def create_default_agency() -> AgentManager:
    manager = AgentManager()

    # --- 1. General Assistant ---
    general_agent = Agent(AgentConfig(
        name="GeneralAssistant",
        model_name="gemini-1.5-flash", 
        system_instruction="You are a helpful AI assistant. Handle general queries, chit-chat, and simple questions. If a request is specific to coding, system operations, or communication, advise the user.",
        tools=["recall", "remember", "get_time", "get_weather"] 
    ))
    manager.register_agent(general_agent)

    # --- 2. Coder / System Admin ---
    coder_agent = Agent(AgentConfig(
        name="SystemEngineer",
        model_name="gemini-1.5-flash", 
        system_instruction="You are a generic System Engineer. You can manage files, run commands, and write code. BE CAREFUL with system commands. Always verify safe operations.",
        tools=[
            "write_file", "read_file", "list_files", "create_directory", "save_code",
            "run_cmd", "run_script", "launch_app", "system_health"
        ]
    ))
    manager.register_agent(coder_agent)

    # --- 3. Gmail Agent ---
    gmail_agent = Agent(AgentConfig(
        name="GmailAgent",
        model_name="gemini-1.5-flash",
        system_instruction="You are a specialized Gmail Agent. You can fetch unread emails and send emails. Be professional.",
        tools=[
            "fetch_mails", "send_mail"
        ]
    ))
    manager.register_agent(gmail_agent)

    # --- 4. WhatsApp Agent ---
    whatsapp_agent = Agent(AgentConfig(
        name="WhatsAppAgent",
        model_name="gemini-1.5-flash",
        system_instruction="You are a specialized WhatsApp Agent. You can send messages, check status, find contacts, and read messages. CRITICAL: If the WhatsApp server is not running (connection error), use 'whatsapp_server' to start it. If the session is not running, use 'whatsapp_start'.",
        tools=[
            "send_whatsapp", "whatsapp_status", 
            "find_contact", "read_whatsapp_messages",
            "whatsapp_server", "whatsapp_start"
        ]
    ))
    manager.register_agent(whatsapp_agent)
    
    # --- 5. Calendar Agent ---
    calendar_agent = Agent(AgentConfig(
        name="CalendarAgent",
        model_name="gemini-1.5-flash",
        system_instruction="You are a specialized Calendar Agent. You can check events and add new events.",
        tools=[
             "add_task", "check_events", "add_event"
        ]
    ))
    manager.register_agent(calendar_agent)

    return manager
