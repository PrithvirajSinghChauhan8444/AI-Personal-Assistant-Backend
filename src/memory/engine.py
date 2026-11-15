"""Unified Layer 5 Memory Engine coordinating 3-tier memory persistence."""

import asyncio
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv("config/.env")
load_dotenv(".env")

from src.agents.contracts import MemoryEngineProtocol
from src.memory.contracts import ReflectionAction
from src.memory.embeddings import EmbeddingEngineProtocol, create_embedder
from src.memory.reflection import MemoryReflectionAgent
from src.memory.tier1_profile import UserProfileManager
from src.memory.tier2_accounts import AccountsContextManager
from src.memory.tier3_storage import EpisodicMemoryStore
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
    """Orchestrates Tier 1 Profile, Tier 2 Accounts, Tier 3 Vector RAG, and Reflection."""

    def __init__(
        self,
        base_dir: Optional[str] = None,
        embedder: Optional[EmbeddingEngineProtocol] = None,
        reflection_client: Optional[BaseLLMClient] = None,
    ) -> None:
        self.config = load_memory_config()
        self.base_dir = resolve_memory_base_dir(base_dir)

        profile_path = os.path.join(self.base_dir, "core_profile.md")
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

    # MemoryEngineProtocol Implementation
    def is_memory_tool(self, tool_name: str) -> bool:
        """Determines if the given tool identifier belongs to Layer 5 local cognitive tools."""
        return tool_name in (
            "memory_update_profile",
            "memory_update_account",
            "memory_store_fact",
            "memory_search",
            "memory_delete",
        )

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Executes a local memory tool in-process with 0ms IPC latency."""
        if tool_name == "memory_update_profile":
            return self._handle_update_profile(arguments)
        elif tool_name == "memory_update_account":
            return self._handle_update_account(arguments)
        elif tool_name == "memory_store_fact":
            return self._handle_store_fact(arguments)
        elif tool_name == "memory_search":
            return self._handle_search(arguments)
        elif tool_name == "memory_delete":
            return self._handle_delete(arguments)
        else:
            return f"Error: Unknown memory tool '{tool_name}'."

    def build_grounding_prompt(self) -> str:
        """Assembles Tier 1 Core Profile and Tier 2 Accounts into the agent grounding context."""
        parts = [
            "=== User Context and Memory Grounding ===",
            "",
            self.profile.get_profile_markdown(),
            "",
            self.accounts.get_accounts_summary(),
        ]
        return "\n".join(parts).strip()

    def schedule_background_reflection(
        self,
        user_prompt: str,
        assistant_response: str,
        recent_history: Optional[List[Dict[str, Any]]] = None,
    ) -> asyncio.Task[None]:
        """Spawns an asynchronous background task to evaluate and curate memory."""
        return asyncio.create_task(
            self.evaluate_turn_and_commit(
                user_prompt=user_prompt,
                assistant_response=assistant_response,
                recent_history=recent_history,
            )
        )

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

        for action in actions:
            if action.action_type == "update_profile" and action.section and action.key:
                self.profile.update_profile(
                    section=action.section,
                    key=action.key,
                    value=action.value or "",
                )
            elif action.action_type == "store_fact" and action.content:
                self.storage.store_fact(
                    content=action.content,
                    category=action.category or "note",
                    tags=action.tags,
                )

        return actions

    # Internal Tool Handlers
    def _handle_update_profile(self, args: Dict[str, Any]) -> str:
        section = str(args.get("section", "")).strip()
        key = str(args.get("key", "")).strip()
        value = str(args.get("value", "")).strip()

        if not section or not key:
            return "Error: 'section' and 'key' are required for memory_update_profile."

        return self.profile.update_profile(section, key, value)

    def _handle_update_account(self, args: Dict[str, Any]) -> str:
        alias = str(args.get("alias", "")).strip().lower()
        email = str(args.get("email", "")).strip().lower()
        provider = str(args.get("provider", "google")).strip().lower()

        if not email:
            if not alias:
                return "Error: 'alias' or 'email' parameter is required for memory_update_account."
            deleted = self.accounts.delete_account(alias)
            if deleted:
                return f"Successfully removed account alias '{alias}' from accounts.md."
            return f"Account alias '{alias}' was not found in accounts.md."

        assigned_alias = self.accounts.update_account(alias=alias or None, email=email, provider=provider)
        return f"Successfully saved account '{assigned_alias}' ({email}, provider: {provider}) to accounts.md."

    def _handle_store_fact(self, args: Dict[str, Any]) -> str:
        # Accepts 'content' with fallback alias 'fact'
        content = str(args.get("content") or args.get("fact") or "").strip()
        if not content:
            return "Error: 'content' (or 'fact') is required for memory_store_fact."

        category = str(args.get("category", "note")).strip()
        tags = args.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        record = self.storage.store_fact(
            content=content,
            category=category,
            tags=tags,
        )
        return f"Stored memory record successfully: [ID: {record.id}, Category: {record.category}]"

    def _handle_search(self, args: Dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' parameter is required for memory_search."

        category = args.get("category")
        if category is not None:
            category = str(category).strip() or None

        # Accepts 'top_k' with fallback alias 'limit'
        top_k_raw = args.get("top_k", args.get("limit", 3))
        try:
            top_k = int(top_k_raw)
        except (ValueError, TypeError):
            top_k = 3

        response = self.storage.search(query=query, category=category, top_k=top_k)
        return response.format_text()

    def _handle_delete(self, args: Dict[str, Any]) -> str:
        mem_id = str(args.get("memory_id", "")).strip()
        if not mem_id:
            return "Error: 'memory_id' is required for memory_delete."

        reason = args.get("reason")
        success = self.storage.delete(memory_id=mem_id, reason=reason)
        if success:
            return f"Deleted memory record '{mem_id}'."
        return f"Memory record '{mem_id}' not found."
