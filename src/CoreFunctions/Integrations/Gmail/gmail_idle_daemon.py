import os
import time
import base64
import select
import imaplib
import threading
from src.CoreFunctions.Infrastructure.auth_utils import get_valid_credentials, load_google_accounts
from src.CoreFunctions.Integrations.Gmail.gmail_reader import fetch_unread_emails_detailed
from src.CoreFunctions.Integrations.Automation.scheduler_ops import speak_text, trigger_desktop_notification, play_beep

def generate_xoauth2_string(email: str, access_token: str) -> str:
    """Generates the raw SASL XOAUTH2 authentication string (not base64 encoded)."""
    return f"user={email}\x01auth=Bearer {access_token}\x01\x01"

class GmailAccountIdleWorker:
    """Manages a persistent IMAP IDLE connection for a single Google account."""
    def __init__(self, account_alias: str, email: str):
        self.account_alias = account_alias
        self.email = email
        self.running = True
        self.thread = None

    def start(self):
        """Starts the background worker thread."""
        self.thread = threading.Thread(
            target=self._run_idle_loop,
            name=f"GmailIdleWorker_{self.account_alias}",
            daemon=True
        )
        self.thread.start()

    def _run_idle_loop(self):
        print(f"📧 [Gmail IDLE - {self.account_alias}] Starting background loop for {self.email}...")
        while self.running:
            try:
                # 1. Fetch valid credentials and access token
                # This will automatically refresh the token using refresh token if expired
                creds = get_valid_credentials(self.account_alias)
                if not creds or not creds.token:
                    raise Exception(f"Failed to load valid credentials for {self.account_alias}")
                
                access_token = creds.token
                
                # 2. Establish connection to Gmail IMAP
                imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
                xoauth_raw = generate_xoauth2_string(self.email, access_token)
                
                # Authenticate using XOAUTH2 (imaplib will automatically base64 encode this raw string)
                imap.authenticate('XOAUTH2', lambda x: xoauth_raw.encode('utf-8'))
                imap.select("INBOX")
                
                # 3. Enter IDLE mode
                tag = imap._new_tag()
                # In Python 3, _new_tag returns string (e.g. 'A01'). Send command to server
                imap.send(f"{tag} IDLE\r\n".encode('utf-8'))
                
                # Read initial '+ idling' response
                resp = imap.readline()
                if not resp.startswith(b'+'):
                    raise Exception(f"Server refused IDLE command: {resp.decode('utf-8', errors='ignore')}")
                
                print(f"✅ [Gmail IDLE - {self.account_alias}] Active watch established on {self.email}")
                
                # 4. Monitor socket using select
                last_refresh = time.time()
                # We refresh the connection every 25 minutes (Google drops IDLE connections after 29 mins)
                refresh_interval = 25 * 60
                
                while self.running and (time.time() - last_refresh < refresh_interval):
                    # select.select blocks until there is socket activity or the 30s timeout expires
                    ready = select.select([imap.socket()], [], [], 30)
                    if ready[0]:
                        line = imap.readline()
                        if not line:
                            raise ConnectionError("IMAP connection closed by remote server.")
                        
                        # An email event looks like: * 42 EXISTS
                        if b"EXISTS" in line:
                            print(f"🔔 [Gmail IDLE - {self.account_alias}] Mailbox update detected!")
                            
                            # Exit IDLE mode to fetch the email details
                            imap.send(b"DONE\r\n")
                            imap.readline() # Consume the trailing server response (e.g., tag OK IDLE completed)
                            
                            # Run the agent workflow asynchronously in a separate worker thread
                            threading.Thread(
                                target=self._trigger_agent_workflow,
                                name=f"GmailIdleTrigger_{self.account_alias}_{int(time.time())}",
                                daemon=True
                            ).start()
                            
                            # Re-enter IDLE mode
                            tag = imap._new_tag()
                            imap.send(f"{tag} IDLE\r\n".encode('utf-8'))
                            resp = imap.readline()
                            if not resp.startswith(b'+'):
                                raise Exception(f"Failed to resume IDLE: {resp.decode('utf-8', errors='ignore')}")
                                
                # Graceful reconnect recycle
                imap.send(b"DONE\r\n")
                imap.readline()
                imap.logout()
                
            except Exception as e:
                print(f"⚠️ [Gmail IDLE - {self.account_alias}] Error occurred: {e}. Re-establishing connection in 15 seconds...")
                time.sleep(15)

    def _trigger_agent_workflow(self):
        """Fetches the latest email details and runs the LangGraph agent state machine."""
        try:
            # 1. Fetch latest unread email details
            res = fetch_unread_emails_detailed(limit=1, account=self.account_alias)
            if "error" in res or not res.get("emails"):
                return
                
            latest_email = res["emails"][0]
            sender = latest_email["sender"]
            subject = latest_email["subject"]
            body_preview = latest_email.get("body", "")
            email_id = latest_email["id"]
            
            # Clean outer XML tags from gmail_reader if present to avoid nested/malformed slicing
            if subject.startswith("<email_subject>") and subject.endswith("</email_subject>"):
                subject = subject[len("<email_subject>"):-len("</email_subject>")]
            if body_preview.startswith("<email_body>") and body_preview.endswith("</email_body>"):
                body_preview = body_preview[len("<email_body>"):-len("</email_body>")]

            goal = (
                f"An email was received in your {self.account_alias} account.\n"
                f"<email_metadata>\n"
                f"Sender: {sender}\n"
                f"Subject: {subject}\n"
                f"</email_metadata>\n"
                f"<email_body_preview>\n"
                f"{body_preview[:200].strip()}\n"
                f"</email_body_preview>\n"
                "Assess if urgent action or a draft response is required."
            )
            
            print(f"🤖 [Gmail IDLE - {self.account_alias}] Dispatching LangGraph Agent for mail ID: {email_id}...")
            
            # Late import to prevent circular import dependency on app
            from src.CoreFunctions.StateGraph.main_graph import app
            
            config = {"configurable": {"thread_id": f"proactive_mail_{self.account_alias}_{email_id}"}}
            initial_state = {
                "primary_goal": goal,
                "active_subtasks": [],
                "working_memory": {},
                "completed_tasks": {},
                "final_response": "",
                "chat_history": []
            }
            
            # Execute LangGraph workflow synchronously inside this background worker thread
            res_state = app.invoke(initial_state, config=config)
            
            final_response = res_state.get("final_response", "")
            if final_response:
                print(f"✅ [Gmail IDLE - {self.account_alias}] Agent executed successfully.")
                
                # Desktop notifications and alert beep
                play_beep()
                trigger_desktop_notification(
                    f"Gmail Assistant ({self.account_alias})",
                    final_response
                )
                
        except Exception as e:
            print(f"❌ [Gmail IDLE - {self.account_alias}] Agent invocation failed: {e}")

class GmailIdleDaemonManager:
    """Coordinates and manages background IDLE connections for all configured Google accounts."""
    def __init__(self):
        self.workers = []
        self.running = False

    def start_all(self):
        """Discovers active accounts and starts their respective IDLE workers after sequential pre-authentication."""
        if self.running:
            return
            
        accounts = load_google_accounts()
        
        # Step 1: Pre-authenticate all accounts sequentially on the main thread
        # to avoid concurrent browser local server port collisions
        valid_accounts = {}
        for alias, email in accounts.items():
            if email and email.strip():
                print(f"🔑 [Gmail IDLE Manager] Pre-authenticating '{alias}' ({email.strip()})...", flush=True)
                try:
                    creds = get_valid_credentials(alias)
                    if creds and creds.token:
                        valid_accounts[alias] = email.strip()
                        print(f"✅ [Gmail IDLE Manager] '{alias}' authenticated successfully.", flush=True)
                    else:
                        print(f"❌ [Gmail IDLE Manager] Failed to get credentials for '{alias}'.", flush=True)
                except Exception as e:
                    print(f"❌ [Gmail IDLE Manager] Error authenticating '{alias}': {e}", flush=True)

        # Step 2: Start background worker threads for successfully authenticated accounts
        self.running = True
        for alias, email in valid_accounts.items():
            worker = GmailAccountIdleWorker(alias, email)
            worker.start()
            self.workers.append(worker)
                
        if not self.workers:
            print("⚠️ [Gmail IDLE Manager] No configured Gmail accounts found or authenticated. Daemon disabled.")

    def stop_all(self):
        """Stops all running IDLE workers."""
        self.running = False
        for worker in self.workers:
            worker.running = False
        self.workers.clear()
