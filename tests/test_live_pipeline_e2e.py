import os
import unittest
import json
from dotenv import load_dotenv

# Load credentials and environment variables
load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["AUTO_APPROVE_CRITICAL_ACTIONS"] = "true"

from modules.contracts.state_contract import AgentState
from modules.contracts.task_contract import WorkerCapability
from modules.task_router.router import TaskRouter
from modules.orchestrator.scheduler import TaskScheduler
from modules.synthesizer.finalizer import OutputSynthesizer
from modules.synthesizer.reflection import ReflectionEngine
from modules.workers.system_worker.worker import SystemWorker
from modules.workers.communication_worker.worker import CommunicationWorker
from modules.workers.productivity_worker.worker import ProductivityWorker
from modules.workers.system_worker.tools.system_tools import get_system_health, read_file_tool, create_file_tool
from modules.workers.productivity_worker.tools.productivity_tools import get_current_time, list_calendar_events
from modules.workers.communication_worker.tools.gmail_tools import fetch_unread_emails
from modules.integration.application_orchestrator import ApplicationOrchestrator

class TestToolsAndPipelineInDepth(unittest.TestCase):
    """In-depth verification of all tools, individual agents, and end-to-end pipeline execution."""

    # ----------------------------------------------------
    # 1. TOOL LEVEL VERIFICATION
    # ----------------------------------------------------
    def test_01_system_tools(self):
        """Verify SystemWorker tools execute and return valid data."""
        # Diagnostic tool
        health = get_system_health.invoke({})
        self.assertIn("CPU:", health)
        self.assertIn("RAM:", health)
        print(f"\n[Tool Check] get_system_health: {health}")

        # File tools
        test_file = "workspace/test_diagnostic.txt"
        create_res = create_file_tool.invoke({"file_path": test_file, "content": "Pipeline diagnostic check 123"})
        self.assertTrue("created successfully" in create_res or "aborted" in create_res)

        if os.path.exists(test_file):
            content = read_file_tool.invoke({"file_path": test_file})
            self.assertEqual(content, "Pipeline diagnostic check 123")
            os.remove(test_file)

    def test_02_productivity_tools(self):
        """Verify ProductivityWorker tools execute and return valid time/events."""
        time_res = get_current_time.invoke({})
        self.assertIn("Current time is:", time_res)
        print(f"[Tool Check] get_current_time: {time_res}")

        events = list_calendar_events.invoke({"max_results": 2})
        self.assertTrue("Calendar" in events or "No upcoming" in events)
        print(f"[Tool Check] list_calendar_events: {events[:100]}...")

    def test_03_communication_tools(self):
        """Verify CommunicationWorker tools execute."""
        unread = fetch_unread_emails.invoke({"max_count": 2})
        self.assertTrue("emails" in unread.lower() or "inbox" in unread.lower() or "unread" in unread.lower())
        print(f"[Tool Check] fetch_unread_emails: {unread[:100]}...")

    # ----------------------------------------------------
    # 2. INDIVIDUAL AGENT LIVE EXECUTION (Tool Reasoning)
    # ----------------------------------------------------
    def test_04_system_worker_agent_live(self):
        """Verify SystemWorker uses tools and responds properly via LLM."""
        worker = SystemWorker()
        result = worker.execute_task(
            task_id="sys_live_1",
            description="Check my current system health and tell me the CPU and RAM percentage.",
            context={}
        )
        self.assertEqual(result["status"], "completed")
        summary = result["summary"].lower()
        self.assertTrue("cpu" in summary or "ram" in summary or "health" in summary)
        print(f"\n[Agent Reply] SystemWorker: {result['summary']}")

    def test_05_productivity_worker_agent_live(self):
        """Verify ProductivityWorker uses get_current_time and answers properly."""
        worker = ProductivityWorker()
        result = worker.execute_task(
            task_id="prod_live_1",
            description="What is the current time?",
            context={}
        )
        self.assertEqual(result["status"], "completed")
        summary = result["summary"].lower()
        self.assertTrue("current time" in summary or "utc" in summary or "time is" in summary)
        print(f"\n[Agent Reply] ProductivityWorker: {result['summary']}")

    # ----------------------------------------------------
    # 3. TASK ROUTER LIVE DECOMPOSITION
    # ----------------------------------------------------
    def test_06_task_router_live(self):
        """Verify TaskRouter decomposes a multi-intent request into a valid DAG."""
        router = TaskRouter()
        capabilities = [
            WorkerCapability(name="SystemWorker", description="Handles system health, file operations"),
            WorkerCapability(name="GmailWorker", description="Handles emails"),
            WorkerCapability(name="ProductivityWorker", description="Handles calendar and tasks")
        ]
        plan = router.route(
            goal="Check my system health and also check unread emails",
            available_workers=capabilities
        )
        self.assertGreaterEqual(len(plan.subtasks), 1)
        workers_assigned = [st.assigned_worker for st in plan.subtasks]
        self.assertTrue("SystemWorker" in workers_assigned or "GmailWorker" in workers_assigned)
        print(f"\n[Router Plan] Planned {len(plan.subtasks)} subtasks: {workers_assigned}")

    # ----------------------------------------------------
    # 4. OUTPUT SYNTHESIZER LIVE
    # ----------------------------------------------------
    def test_07_synthesizer_live(self):
        """Verify OutputSynthesizer generates natural language answer from task outputs."""
        synthesizer = OutputSynthesizer()
        completed = {
            "task_1": {
                "worker": "SystemWorker",
                "description": "Check CPU",
                "summary": "CPU is running at 18%, RAM is at 45%."
            }
        }
        reply = synthesizer.synthesize("What is my system load?", completed)
        self.assertIsInstance(reply, str)
        self.assertTrue(len(reply) > 20)
        print(f"\n[Synthesizer Reply]: {reply}")

    # ----------------------------------------------------
    # 5. COMPLETE MULTI-AGENT PIPELINE E2E
    # ----------------------------------------------------
    def test_08_full_pipeline_live_e2e(self):
        """Verify complete pipeline: Router -> Orchestrator -> SystemWorker -> Finalizer -> Telemetry."""
        app = ApplicationOrchestrator()
        prompt = "Report my current CPU and memory diagnostics."
        final_answer = app.run(prompt)

        self.assertIsInstance(final_answer, str)
        self.assertTrue(len(final_answer) > 20)
        self.assertTrue("cpu" in final_answer.lower() or "ram" in final_answer.lower() or "memory" in final_answer.lower())
        print(f"\n=======================================================")
        print(f"🤖 FULL PIPELINE LIVE RESPONSE:")
        print(final_answer)
        print(f"=======================================================\n")

        # Verify OpenTelemetry trace was recorded
        traces_file = "Memory/logs/otel_traces.jsonl"
        self.assertTrue(os.path.exists(traces_file))
        with open(traces_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertTrue(len(lines) > 0)
            print(f"[Telemetry] Verified {len(lines)} OpenTelemetry spans written to {traces_file}.")

if __name__ == "__main__":
    unittest.main()
