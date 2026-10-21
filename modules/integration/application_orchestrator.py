import os
import uuid
from typing import Dict, Any, List, Optional, Callable

from modules.contracts.state_contract import AgentState
from modules.task_router.router import TaskRouter
from modules.orchestrator.scheduler import TaskScheduler
from modules.synthesizer.finalizer import OutputSynthesizer
from modules.synthesizer.reflection import ReflectionEngine
from modules.workers import (
    SystemWorker,
    CommunicationWorker,
    ProductivityWorker,
    BrowserWorker,
    GithubWorker,
    ClassroomWorker,
    GoogleDriveWorker,
    YoutubeWorker,
    ResearchWorker,
    ObsidianWorker,
    MemoryWorker,
    MiscWorker
)
from modules.infrastructure.observability.logger import ModuleLogger
from modules.infrastructure.storage.unified_storage import UnifiedStorage
from modules.infrastructure.observability.telemetry import TelemetryManager, get_module_tracer
from modules.integration.pipeline_builder import build_modular_pipeline

tracer = get_module_tracer("integration")

class ApplicationOrchestrator:
    """The Final Integration Module.
    Wires all decoupled modules into the end-to-end conversational flow,
    manages execution streams, session checkpoints, and state persistence.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # Ensure telemetry is initialized
        TelemetryManager.initialize(service_name=self.config.get("service_name", "ai-personal-assistant"))

        self.storage = UnifiedStorage()
        self.logger = ModuleLogger()

        # Initialize decoupled cognitive modules
        self.router = TaskRouter()
        self.scheduler = TaskScheduler(allow_parallel=True)
        self.synthesizer = OutputSynthesizer()
        self.reflection = ReflectionEngine()

        # Instantiate workers
        self.workers = [
            SystemWorker(),
            CommunicationWorker(),
            ProductivityWorker(),
            BrowserWorker(),
            GithubWorker(),
            ClassroomWorker(),
            GoogleDriveWorker(),
            YoutubeWorker(),
            ResearchWorker(),
            ObsidianWorker(),
            MemoryWorker(),
            MiscWorker()
        ]

        # Compile full graph
        self.pipeline = build_modular_pipeline(
            router=self.router,
            scheduler=self.scheduler,
            synthesizer=self.synthesizer,
            reflection=self.reflection,
            workers=self.workers
        )

    def run(
        self,
        user_prompt: str,
        thread_id: Optional[str] = None,
        verbose: bool = False,
        chat_history: Optional[List[Dict[str, str]]] = None,
        working_memory: Optional[Dict[str, Any]] = None,
        completed_tasks: Optional[Dict[str, Any]] = None,
        on_progress: Optional[Callable[[str], None]] = None,
        on_node_transition: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> str:
        """Executes the complete request lifecycle across all independent modules."""
        thread_id = thread_id or f"session_{uuid.uuid4().hex[:8]}"
        run_config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
        is_verbose = verbose or os.environ.get("VERBOSE") in ("1", "true", "True")

        with tracer.start_as_current_span("application.process_request") as root_span:
            root_span.set_attribute("session.thread_id", thread_id)
            root_span.set_attribute("session.goal", user_prompt)

            self.logger.log_event("ApplicationOrchestrator", "session_start", {
                "thread_id": thread_id,
                "goal": user_prompt
            })

            # Setup initial state with incoming context or restore
            initial_wm = dict(working_memory or {})
            
            # Dynamic Account Grounding: Inject active configured accounts into user_profile
            try:
                from modules.infrastructure.security.oauth import load_google_accounts
                google_accs = load_google_accounts()
                active_accs = {k: v for k, v in google_accs.items() if v and str(v).strip()}
                if active_accs:
                    up = initial_wm.setdefault("user_profile", {})
                    up["configured_accounts"] = active_accs
                    acc_summary = [f"{alias}: {email}" for alias, email in active_accs.items()]
                    up["active_account_aliases"] = ", ".join(acc_summary)
            except Exception as acc_err:
                self.logger.log_event("ApplicationOrchestrator", "account_grounding_error", {"error": str(acc_err)})

            initial_state: AgentState = {
                "primary_goal": user_prompt,
                "active_subtasks": [],
                "working_memory": initial_wm,
                "completed_tasks": dict(completed_tasks or {}),
                "final_response": "",
                "error_logs": [],
                "chat_history": list(chat_history or [])
            }

            # 1. Save initial interrupted checkpoint
            from modules.infrastructure.storage.session_manager import (
                save_interrupted_task_checkpoint,
                clear_interrupted_task_checkpoint,
                save_session_context_async
            )
            save_interrupted_task_checkpoint(initial_state, status="running")

            if on_progress:
                try:
                    on_progress("🧠 Understanding query & planning execution...")
                except Exception:
                    pass

            final_response = ""
            current_state_snapshot = initial_state
            try:
                for event in self.pipeline.stream(initial_state, config=run_config):
                    for node_name, state_update in event.items():
                        self.logger.log_event(node_name, "node_transition", state_update)
                        if on_node_transition:
                            try:
                                on_node_transition(node_name, state_update)
                            except Exception:
                                pass
                        
                        # Update checkpoint as tasks progress
                        try:
                            state_snapshot = self.pipeline.get_state(run_config)
                            if state_snapshot and state_snapshot.values:
                                current_state_snapshot = state_snapshot.values
                                save_interrupted_task_checkpoint(state_snapshot.values, status="running")
                        except Exception:
                            pass

                        if on_progress:
                            try:
                                if node_name == "TaskRouter":
                                    tasks = state_update.get("active_subtasks", [])
                                    if tasks:
                                        assigned = list(dict.fromkeys(t.get("assigned_worker") for t in tasks if t.get("assigned_worker")))
                                        on_progress(f"📋 Planned {len(tasks)} subtask(s) via {', '.join(assigned)}...")
                                    else:
                                        on_progress("⚡ Direct response planned...")
                                elif node_name == "Orchestrator":
                                    nxt = state_update.get("next_node")
                                    if nxt and nxt != "OutputFinalizer":
                                        targets = nxt if isinstance(nxt, list) else [nxt]
                                        on_progress(f"🚀 Dispatching to {', '.join(targets)}...")
                                elif node_name == "OutputFinalizer":
                                    on_progress("✍️ Synthesizing final response...")
                                elif node_name == "Reflection":
                                    pass
                                else:
                                    completed = state_update.get("completed_tasks", {})
                                    summary = ""
                                    for _, c_data in completed.items():
                                        summary = c_data.get("summary", "")[:80].replace("\n", " ")
                                    if summary:
                                        on_progress(f"⚡ {node_name} finished: {summary}...")
                                    else:
                                        on_progress(f"⚡ {node_name} completed task...")
                            except Exception:
                                pass

                        if is_verbose:
                            if node_name == "TaskRouter":
                                tasks = state_update.get("active_subtasks", [])
                                print(f"📋 [TaskRouter] Planned {len(tasks)} subtask(s):")
                                for t in tasks:
                                    deps = f" (depends on {t.get('depends_on')})" if t.get('depends_on') else ""
                                    print(f"   ↳ [{t.get('id')}] -> {t.get('assigned_worker')}: {t.get('description')}{deps}")
                            elif node_name == "Orchestrator":
                                nxt = state_update.get("next_node")
                                print(f"🧭 [Orchestrator] Next execution target: {nxt}")
                            elif node_name == "OutputFinalizer":
                                print(f"✨ [OutputFinalizer] Synthesizing final response...")
                            elif node_name == "Reflection":
                                pass
                            else:
                                completed = state_update.get("completed_tasks", {})
                                summary = ""
                                for _, c_data in completed.items():
                                    summary = c_data.get("summary", "")[:120].replace("\n", " ")
                                print(f"⚡ [{node_name}] Done{f' → {summary}...' if summary else ''}")

                state_snapshot = self.pipeline.get_state(run_config)
                final_response = state_snapshot.values.get("final_response", "")

                root_span.set_attribute("session.status", "completed")
                root_span.set_attribute("session.final_response_length", len(final_response))

                self.logger.log_event("ApplicationOrchestrator", "session_complete", {
                    "thread_id": thread_id,
                    "final_response": final_response
                })

                # 2. Clean exit: clear interrupted checkpoint and persist conversation session
                clear_interrupted_task_checkpoint()
                
                updated_history = list(chat_history or [])
                updated_history.append({"role": "user", "content": user_prompt})
                if final_response:
                    updated_history.append({"role": "assistant", "content": final_response})

                save_session_context_async(
                    chat_history=updated_history,
                    working_memory=state_snapshot.values.get("working_memory", {}),
                    completed_tasks=state_snapshot.values.get("completed_tasks", {}),
                    session_id=thread_id
                )

            except KeyboardInterrupt:
                save_interrupted_task_checkpoint(current_state_snapshot, status="interrupted")
                final_response = "Execution was interrupted by user. State checkpoint saved."
                if is_verbose:
                    print(f"\n⚠️ [Interrupted]: Task checkpoint saved.")
            except Exception as e:
                save_interrupted_task_checkpoint(current_state_snapshot, status="interrupted")
                root_span.record_exception(e)
                root_span.set_attribute("session.status", "error")
                self.logger.log_event("ApplicationOrchestrator", "session_error", {
                    "error": str(e)
                })
                if is_verbose:
                    import traceback
                    print(f"❌ [Error]: {e}")
                    traceback.print_exc()
                final_response = f"An execution error occurred: {e}"

            return final_response

    @staticmethod
    def get_interrupted_checkpoint() -> Optional[Dict[str, Any]]:
        from modules.infrastructure.storage.session_manager import get_interrupted_task
        return get_interrupted_task()

    @staticmethod
    def clear_interrupted_checkpoint() -> None:
        from modules.infrastructure.storage.session_manager import clear_interrupted_task_checkpoint
        clear_interrupted_task_checkpoint()

    @staticmethod
    def get_saved_session() -> Optional[Dict[str, Any]]:
        from modules.infrastructure.storage.session_manager import load_session_context
        return load_session_context()

    @staticmethod
    def clear_saved_session() -> None:
        from modules.infrastructure.storage.session_manager import clear_session_context
        clear_session_context()

    def get_pipeline_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves current values snapshot for a specific conversation thread."""
        try:
            snapshot = self.pipeline.get_state({"configurable": {"thread_id": thread_id}})
            return snapshot.values if snapshot else None
        except Exception:
            return None


