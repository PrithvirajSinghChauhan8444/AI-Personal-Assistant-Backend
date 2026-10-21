import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from modules.adapters.remote_control.exporter import ConversationExporter
from modules.infrastructure.storage.session_manager import save_session_context_async
from modules.integration.application_orchestrator import ApplicationOrchestrator

logger = logging.getLogger("RemoteControlCoordinator")


@dataclass
class ConversationTurn:
    """Represents a single query-response turn within the shared remote control session."""
    turn_id: int
    source: str  # "cli" or "telegram"
    user_prompt: str
    assistant_response: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    completed_tasks: Dict[str, Any] = field(default_factory=dict)
    working_memory_snapshot: Dict[str, Any] = field(default_factory=dict)
    node_transitions: List[Dict[str, Any]] = field(default_factory=list)
    error_logs: List[str] = field(default_factory=list)


class RemoteControlCoordinator:
    """
    Manages dual-mode interactions (CLI & Telegram) in a single unified session.
    
    Rules enforced:
    1. Active Source Shift: Does not continuously mirror the conversation back and forth.
       Only shifts active context when user queries from the other source.
    2. On-Demand Export: Allows user on either source to export clean or verbose
       conversation transcripts (terminal print or file export).
    """

    def __init__(
        self,
        orchestrator: Optional[ApplicationOrchestrator] = None,
        session_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        working_memory: Optional[Dict[str, Any]] = None,
        completed_tasks: Optional[Dict[str, Any]] = None,
    ):
        self._orchestrator = orchestrator or ApplicationOrchestrator()
        self.session_id: str = session_id or f"remote_{uuid.uuid4().hex[:8]}"

        # Shared conversational state across all sources
        self.chat_history: List[Dict[str, Any]] = list(chat_history or [])
        self.working_memory: Dict[str, Any] = dict(working_memory or {})
        self.completed_tasks: Dict[str, Any] = dict(completed_tasks or {})
        self.turns: List[ConversationTurn] = []

        # Current active source ("cli", "telegram", or None)
        self.active_source: Optional[str] = None

        # Thread safety lock for concurrent execution requests
        self._execution_lock = threading.Lock()

        # Listeners for source shifts (e.g. CLI UI notifications)
        self._shift_listeners: List[Callable[[str, str], None]] = []

        # Reference to background Telegram adapter if active
        self._telegram_adapter: Optional[Any] = None

    @property
    def orchestrator(self) -> ApplicationOrchestrator:
        return self._orchestrator

    @property
    def telegram_adapter(self) -> Optional[Any]:
        return self._telegram_adapter

    def register_shift_listener(self, callback: Callable[[str, str], None]) -> None:
        """Registers a callback when active source transitions (old_source, new_source)."""
        if callback not in self._shift_listeners:
            self._shift_listeners.append(callback)

    def unregister_shift_listener(self, callback: Callable[[str, str], None]) -> None:
        if callback in self._shift_listeners:
            self._shift_listeners.remove(callback)

    def shift_source(self, new_source: str) -> bool:
        """
        Shifts the active conversation source.
        Returns True if a shift occurred, False if source was already active.
        """
        old_source = self.active_source
        if old_source != new_source:
            self.active_source = new_source
            logger.info(f"Conversation source shifted: [{old_source or 'INITIAL'}] ➔ [{new_source}]")

            for listener in list(self._shift_listeners):
                try:
                    listener(old_source or "NONE", new_source)
                except Exception as err:
                    logger.warning(f"Error notifying shift listener: {err}")
            return True
        return False

    def execute_query(
        self,
        user_prompt: str,
        source: str,
        verbose: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Executes user query within the unified session.
        Shifts active source, executes pipeline, records turn details,
        and synchronizes shared working memory and conversation history.
        """
        # Rule 1: Shift conversation to this source
        self.shift_source(source)

        node_transitions: List[Dict[str, Any]] = []

        def _transition_hook(node_name: str, update: Dict[str, Any]) -> None:
            node_transitions.append({
                "node": node_name,
                "next_node": update.get("next_node", ""),
                "timestamp": datetime.now().isoformat(),
            })

        acquired = self._execution_lock.acquire(timeout=120.0)
        if not acquired:
            return "⚠️ The assistant is currently busy processing another request. Please try again shortly."

        try:
            timestamp = datetime.now().isoformat()

            # Execute via core orchestrator pipeline with snapshot of current history
            response = self.orchestrator.run(
                user_prompt=user_prompt,
                thread_id=self.session_id,
                verbose=verbose,
                chat_history=list(self.chat_history),
                working_memory=self.working_memory,
                completed_tasks=self.completed_tasks,
                on_progress=on_progress,
                on_node_transition=_transition_hook,
            )

            # Retrieve state snapshot from LangGraph
            state_snapshot = self.orchestrator.get_pipeline_state(self.session_id)
            subtasks = []
            if state_snapshot:
                subtasks = state_snapshot.get("active_subtasks", [])
                # Update shared working memory and completed tasks
                new_wm = state_snapshot.get("working_memory", {})
                if new_wm:
                    self.working_memory.update(new_wm)
                new_completed = state_snapshot.get("completed_tasks", {})
                if new_completed:
                    self.completed_tasks.update(new_completed)

            # Append to shared chat history with source metadata
            self.chat_history.append({
                "role": "user",
                "content": user_prompt,
                "source": source,
                "timestamp": timestamp,
            })
            if response:
                self.chat_history.append({
                    "role": "assistant",
                    "content": response,
                    "source": source,
                    "timestamp": datetime.now().isoformat(),
                })

            # Record detailed turn data for on-demand clean/verbose exports
            turn = ConversationTurn(
                turn_id=len(self.turns) + 1,
                source=source,
                user_prompt=user_prompt,
                assistant_response=response,
                timestamp=timestamp,
                subtasks=subtasks,
                completed_tasks=dict(self.completed_tasks),
                working_memory_snapshot=dict(self.working_memory),
                node_transitions=node_transitions,
            )
            self.turns.append(turn)

            # Persist session asynchronously
            save_session_context_async(
                chat_history=self.chat_history,
                working_memory=self.working_memory,
                completed_tasks=self.completed_tasks,
                session_id=self.session_id,
            )

            return response
        finally:
            self._execution_lock.release()

    def export_conversation(self, verbose: bool = False) -> str:
        """Generates formatted transcript text (Clean or Verbose)."""
        worker_names = [w.name for w in self.orchestrator.workers] if hasattr(self.orchestrator, "workers") else []
        if verbose:
            return ConversationExporter.format_verbose(
                session_id=self.session_id,
                turns=self.turns,
                active_source=self.active_source,
                registered_workers=worker_names,
            )
        else:
            return ConversationExporter.format_clean(
                session_id=self.session_id,
                turns=self.turns,
                active_source=self.active_source,
                chat_history=self.chat_history,
            )

    def export_conversation_to_file(
        self,
        verbose: bool = False,
        file_path: Optional[str] = None,
        export_dir: Optional[str] = None,
    ) -> str:
        """Exports transcript to file and returns absolute path."""
        content = self.export_conversation(verbose=verbose)
        if file_path:
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return os.path.abspath(file_path)

        return ConversationExporter.save_to_file(
            content=content,
            session_id=self.session_id,
            verbose=verbose,
            export_dir=export_dir,
        )

    def start_telegram_background(
        self,
        token: Optional[str] = None,
        allowed_user_ids: Optional[List[int]] = None,
    ) -> Optional[Any]:
        """
        Initializes and launches the TelegramAdapter in a background thread connected
        to this shared coordinator.
        """
        from modules.adapters.telegram.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(
            token=token,
            allowed_user_ids=allowed_user_ids,
            orchestrator=self.orchestrator,
            coordinator=self,
        )
        self._telegram_adapter = adapter
        adapter.start_background()
        return adapter

    def stop(self) -> None:
        """Stops active adapters and cleans up."""
        if self._telegram_adapter:
            try:
                self._telegram_adapter.stop()
            except Exception as e:
                logger.warning(f"Error stopping Telegram adapter: {e}")
            self._telegram_adapter = None
