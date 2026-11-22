"""Unified Layer 5 Memory Engine coordinating profile, accounts, episodic storage, and reflection."""

import asyncio
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv("config/.env")
load_dotenv(".env")

from src.agents.contracts import MemoryEngineProtocol
from src.memory.contracts import (
    MemoryContextSnapshot,
    MemoryMutationEvent,
    MemoryObserver,
    ReflectionAction,
    RetrievedFactSnapshot,
)
from src.memory.embeddings import EmbeddingEngineProtocol, create_embedder
from src.memory.profiles import AccountsContextManager, UserProfileManager
from src.memory.reflection import MemoryReflectionAgent
from src.memory.storage import EpisodicMemoryStore
from src.memory.tools import MemoryToolExecutor
from src.models.base import BaseLLMClient

DEFAULT_MEMORY_BASE_DIR = "~/.config/ai-assistant/memory"


def resolve_memory_base_dir(base_dir: Optional[str] = None) -> str:
    """Resolves the root directory for Layer 5 memory persistence in a fully portable manner."""
    if base_dir:
        return os.path.abspath(os.path.expanduser(os.path.expandvars(base_dir)))

    env_dir = os.environ.get("AI_ASSISTANT_MEMORY_DIR")
    if env_dir:
        return os.path.abspath(os.path.expanduser(os.path.expandvars(env_dir)))

    try:
        from src.agents.factory import load_system_config
        cfg = load_system_config()
        if "memory_dir" in cfg and cfg["memory_dir"]:
            return os.path.abspath(os.path.expanduser(os.path.expandvars(cfg["memory_dir"])))
        if "workspace_dir" in cfg and cfg["workspace_dir"]:
            return os.path.abspath(
                os.path.expanduser(os.path.expandvars(os.path.join(cfg["workspace_dir"], "Memory")))
            )
    except Exception:
        pass

    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return os.path.abspath(os.path.expanduser(os.path.join(xdg_config, "ai-assistant", "memory")))

    return os.path.abspath(os.path.expanduser(DEFAULT_MEMORY_BASE_DIR))


def load_memory_config() -> Dict[str, Any]:
    """Loads system configuration for memory layer from config/system.json with local overrides."""
    try:
        from src.agents.factory import load_system_config
        return load_system_config()
    except Exception:
        candidates = [
            "config/system.json",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "system.json"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                try:
                    import json
                    with open(c, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
        return {}


class MemoryEngine(MemoryEngineProtocol):
    """Orchestrates User Profile, Accounts Context, Episodic Storage, and Reflection."""

    def __init__(
        self,
        base_dir: Optional[str] = None,
        embedder: Optional[EmbeddingEngineProtocol] = None,
        reflection_client: Optional[BaseLLMClient] = None,
    ) -> None:
        self.config = load_memory_config()
        self.base_dir = resolve_memory_base_dir(base_dir)

        from src.memory.vault.vault_manager import VaultManager
        self.vault = VaultManager(self.base_dir)

        profile_path = str(self.vault.root_dir / "profile.md")
        accounts_path = os.path.join(self.base_dir, "accounts.md")
        db_path = os.path.join(self.base_dir, "storage", "memories.db")
        index_path = os.path.join(self.base_dir, "storage", "faiss_index.bin")

        min_score = float(self.config.get("memory_similarity_threshold", 0.70))
        provider = self.config.get("memory_embedding_provider")
        model_name = self.config.get("memory_embedding_model")

        self.embedder = embedder or create_embedder(provider=provider, model_name=model_name)
        self.profile = UserProfileManager(profile_path)
        self.accounts = AccountsContextManager(accounts_path)
        self.storage = EpisodicMemoryStore(
            db_path=db_path,
            index_path=index_path,
            embedder=self.embedder,
            min_relevance_score=min_score,
        )
        self.reflector = MemoryReflectionAgent(model_client=reflection_client)
        self._observers: List[MemoryObserver] = []
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._recent_turn_facts: set[str] = set()
        self._tool_executor = MemoryToolExecutor(self)

    def register_memory_observer(self, observer: MemoryObserver) -> None:
        """Registers a listener for real-time memory state mutations."""
        if observer not in self._observers:
            self._observers.append(observer)

    def unregister_memory_observer(self, observer: MemoryObserver) -> None:
        """Removes a previously registered memory observer."""
        if observer in self._observers:
            self._observers.remove(observer)

    def _notify_observers(self, event_type: str, details: Dict[str, Any]) -> None:
        event = MemoryMutationEvent(
            event_type=event_type,
            details=details,
            timestamp=time.time(),
        )
        for obs in list(self._observers):
            try:
                obs.on_memory_updated(event)
            except Exception:
                pass

    def get_context_snapshot(
        self, user_id: str = "default", query: Optional[str] = None
    ) -> MemoryContextSnapshot:
        """Assembles a structured snapshot across user profile, accounts, and episodic memory."""
        profile_attrs = dict(self.profile.sections)

        accounts_data = self.accounts.get_accounts_data()
        connected = []
        for acc in accounts_data.get("email_accounts", []):
            connected.append({
                "alias": acc.get("alias", ""),
                "email": acc.get("email", ""),
                "provider": acc.get("provider", "unknown"),
            })

        retrieved_facts: List[RetrievedFactSnapshot] = []
        if query:
            search_resp = self.storage.search(query=query, top_k=5)
            for res in search_resp.results:
                tokens = max(1, len(res.record.content) // 4)
                retrieved_facts.append(
                    RetrievedFactSnapshot(
                        id=res.record.id,
                        content=res.record.content,
                        category=res.record.category,
                        similarity_score=res.score,
                        estimated_tokens=tokens,
                    )
                )

        profile_text = self.profile.get_profile_markdown()
        accounts_text = self.accounts.get_accounts_summary()
        facts_tokens = sum(f.estimated_tokens for f in retrieved_facts)
        total_tokens = (len(profile_text) + len(accounts_text)) // 4 + facts_tokens

        return MemoryContextSnapshot(
            user_id=user_id,
            profile_attributes=profile_attrs,
            connected_accounts=connected,
            retrieved_facts=retrieved_facts,
            total_estimated_tokens=total_tokens,
        )

    # MemoryEngineProtocol Implementation
    def is_memory_tool(self, tool_name: str) -> bool:
        """Determines if tool name belongs to Layer 5 local memory tools."""
        return tool_name in (
            "memory_read",
            "memory_add",
            "memory_remove",
            "memory_create",
            "consult_memory",
            "memory_update_profile",
            "memory_update_account",
            "memory_store_fact",
            "memory_search",
            "memory_delete",
        )

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        session_id: Optional[str] = None,
        turn_id: Optional[str] = None,
    ) -> str:
        """Delegates tool execution to MemoryToolExecutor."""
        return await self._tool_executor.execute(
            tool_name=tool_name,
            arguments=arguments,
            session_id=session_id,
            turn_id=turn_id,
        )

    def build_grounding_prompt(self) -> str:
        """Assembles User Profile and Rules into the agent grounding context."""
        parts = [
            "=== User Context and Memory Grounding ===",
            "",
            self.vault.get_profile_markdown(),
            "",
            self.vault.get_rules_markdown(),
        ]
        return "\n".join(parts).strip()

    def schedule_background_reflection(
        self,
        user_prompt: str,
        assistant_response: str,
        recent_history: Optional[List[Dict[str, Any]]] = None,
    ) -> asyncio.Task[None]:
        """Spawns an asynchronous background task to evaluate and curate memory."""
        task = asyncio.create_task(
            self.evaluate_turn_and_commit(
                user_prompt=user_prompt,
                assistant_response=assistant_response,
                recent_history=recent_history,
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def evaluate_turn_and_commit(
        self,
        user_prompt: str,
        assistant_response: str,
        recent_history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ReflectionAction]:
        """Analyzes recent interaction via LLM reflection and applies mutations."""
        actions = await self.reflector.evaluate_interaction(
            user_prompt=user_prompt,
            assistant_response=assistant_response,
            recent_history=recent_history,
        )

        committed_actions: List[ReflectionAction] = []
        for action in actions:
            if action.action_type == "update_profile" and action.section and action.key:
                self.profile.update_profile(
                    section=action.section,
                    key=action.key,
                    value=action.value or "",
                )
                committed_actions.append(action)
            elif action.action_type == "store_fact" and action.content:
                clean_fact = action.content.strip().lower()
                if clean_fact in self._recent_turn_facts:
                    continue
                self.storage.store_fact(
                    content=action.content,
                    category=action.category or "note",
                    tags=action.tags,
                )
                committed_actions.append(action)
            elif action.action_type == "supersede_fact" and action.target_id and action.content:
                self.storage.delete(action.target_id, reason="superseded_by_reflection")
                self.storage.store_fact(
                    content=action.content,
                    category=action.category or "note",
                    tags=action.tags,
                )
                committed_actions.append(action)
            elif action.action_type == "delete_fact" and action.target_id:
                self.storage.delete(action.target_id, reason=action.reason or "reflection_deleted")
                committed_actions.append(action)

        if committed_actions:
            self._notify_observers("reflection_completed", {"actions_count": len(committed_actions)})

        return committed_actions
