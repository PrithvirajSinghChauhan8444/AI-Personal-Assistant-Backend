import subprocess
import threading
from typing import List, Dict
from langchain_core.tools import StructuredTool

def run_action_callback(action: str):
    """Executes the action associated with the clicked notification button."""
    print(f"⚡ [Notification Callback] Handling action: {action}", flush=True)
    try:
        if action.startswith("run_agent:"):
            goal = action[len("run_agent:"):].strip()
            print(f"🤖 [Callback] Triggering proactive agent with goal: '{goal}'", flush=True)
            
            # Late import of app to prevent circular dependency
            from src.CoreFunctions.StateGraph.main_graph import app
            import uuid
            
            config = {"configurable": {"thread_id": f"callback_mail_{uuid.uuid4().hex[:8]}"}}
            initial_state = {
                "primary_goal": goal,
                "active_subtasks": [],
                "working_memory": {},
                "completed_tasks": {},
                "final_response": "",
                "chat_history": []
            }
            
            # Invoke the graph in a separate thread so we don't block the caller
            threading.Thread(
                target=app.invoke,
                args=(initial_state,),
                kwargs={"config": config},
                daemon=True
            ).start()
            
        elif action.startswith("open_file:"):
            filepath = action[len("open_file:"):].strip()
            print(f"📂 [Callback] Opening file: {filepath}", flush=True)
            # Use xdg-open to launch default desktop handler
            subprocess.run(["xdg-open", filepath], check=False)
            
        elif action.startswith("command:"):
            cmd = action[len("command:"):].strip()
            print(f"💻 [Callback] Running command: {cmd}", flush=True)
            subprocess.run(cmd, shell=True, check=False)
            
        else:
            print(f"ℹ️ [Callback] Action received: '{action}'", flush=True)
    except Exception as e:
        print(f"❌ [Callback] Error executing action: {e}", flush=True)

def trigger_interactive_notification_sync(title: str, message: str, buttons: List[Dict[str, str]]) -> str:
    """
    Triggers a desktop notification with interactive action buttons on Linux.
    
    Args:
        title (str): The main header/title of the notification.
        message (str): The detailed body of the notification.
        buttons (list of dicts): List of button dicts containing:
            - 'label': Text shown on the button (e.g. 'Approve', 'Open Note')
            - 'action': Callback action to execute if clicked.
              Can be:
              - 'run_agent: <goal>' (e.g., 'run_agent: Send the email draft with ID 123')
              - 'open_file: <path>' (e.g., 'open_file: /home/user/notes/draft.md')
              - 'command: <cmd>' (e.g., 'command: echo hello')
              - '<custom_string>' (generic string)
    """
    # Build the notify-send command
    # Format: notify-send "Title" "Message" --action="key1=Label 1" --action="key2=Label 2"
    cmd = ["notify-send", title, message]
    
    # Map action keys to their respective callback payloads
    action_mapping = {}
    for idx, btn in enumerate(buttons):
        label = btn.get("label", "Button")
        action = btn.get("action", "")
        action_key = f"action_{idx}"
        action_mapping[action_key] = action
        cmd.append(f"--action={action_key}={label}")
        
    def run_notification():
        try:
            # Run notify-send. It blocks until clicked or dismissed.
            # It prints the selected action_key to stdout on click.
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            clicked_key = result.stdout.strip()
            
            if clicked_key in action_mapping:
                target_action = action_mapping[clicked_key]
                run_action_callback(target_action)
        except Exception as e:
            print(f"⚠️ [Notification Tool] notify-send failed or timed out: {e}", flush=True)
            
    # Start in background thread so it doesn't block the caller execution thread
    threading.Thread(target=run_notification, daemon=True).start()
    
    return f"Interactive notification '{title}' successfully triggered in background."

# Expose as a LangChain StructuredTool
interactive_notification_tool = StructuredTool.from_function(
    func=trigger_interactive_notification_sync,
    name="trigger_interactive_notification",
    description=(
        "Triggers a desktop notification with interactive action buttons on Linux. "
        "Allows user to approve or click actions, running callbacks in the background."
    )
)
