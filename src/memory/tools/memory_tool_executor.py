"""Executor and dispatcher for Layer 5 local memory tools."""

from typing import Any, Dict, Optional


class MemoryToolExecutor:
    """Validates inputs and dispatches memory tool requests to underlying managers."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        session_id: Optional[str] = None,
        turn_id: Optional[str] = None,
    ) -> str:
        """Executes a memory tool and formats the response."""
        # Universal Vault Tools
        if tool_name == "memory_read":
            return self._handle_vault_read(arguments)
        elif tool_name == "memory_add":
            return self._handle_vault_add(arguments)
        elif tool_name == "memory_remove":
            return self._handle_vault_remove(arguments)
        elif tool_name == "memory_create":
            return self._handle_vault_create(arguments)
        elif tool_name == "consult_memory":
            return self._handle_consult_memory(arguments)
        # Legacy Memory Tools
        elif tool_name == "memory_update_profile":
            return self._handle_update_profile(arguments)
        elif tool_name == "memory_update_account":
            return self._handle_update_account(arguments)
        elif tool_name == "memory_store_fact":
            return self._handle_store_fact(arguments, session_id=session_id, turn_id=turn_id)
        elif tool_name == "memory_search":
            return self._handle_search(arguments)
        elif tool_name == "memory_delete":
            return self._handle_delete(arguments)
        else:
            return f"Error: Unknown memory tool '{tool_name}'."

    def _handle_vault_read(self, args: Dict[str, Any]) -> str:
        return self.engine.vault.read(
            file_path=args.get("file"),
            query=args.get("query"),
            section=args.get("section"),
        )

    def _handle_vault_add(self, args: Dict[str, Any]) -> str:
        file_path = str(args.get("file") or "profile.md").strip()
        section = str(args.get("section") or "General").strip()
        content = str(args.get("content") or "").strip()
        key = args.get("key")
        if not content:
            return "Error: 'content' parameter is required for memory_add."
        return self.engine.vault.add(file_path=file_path, section=section, content=content, key=key)

    def _handle_vault_remove(self, args: Dict[str, Any]) -> str:
        file_path = str(args.get("file") or "profile.md").strip()
        section = str(args.get("section") or "General").strip()
        key = str(args.get("key") or "").strip()
        if not key:
            return "Error: 'key' parameter is required for memory_remove."
        return self.engine.vault.remove(file_path=file_path, section=section, key=key)

    def _handle_vault_create(self, args: Dict[str, Any]) -> str:
        file_path = str(args.get("path") or "").strip()
        desc = str(args.get("description") or "").strip()
        init_content = str(args.get("initial_content") or "")
        if not file_path:
            return "Error: 'path' parameter is required for memory_create."
        return self.engine.vault.create(file_path=file_path, description=desc, initial_content=init_content)

    def _handle_consult_memory(self, args: Dict[str, Any]) -> str:
        query = str(args.get("query") or "").strip()
        if not query:
            return "Error: 'query' parameter is required for consult_memory."
        return self.engine.vault.read(query=query)

    def _handle_update_profile(self, args: Dict[str, Any]) -> str:
        section = str(args.get("section", "")).strip()
        key = str(args.get("key", "")).strip()
        value = str(args.get("value", "")).strip()

        if not section or not key:
            return "Error: 'section' and 'key' are required for memory_update_profile."

        result = self.engine.profile.update_profile(section, key, value)
        self.engine._notify_observers("profile_updated", {"section": section, "key": key, "value": value})
        return result

    def _handle_update_account(self, args: Dict[str, Any]) -> str:
        alias = str(args.get("alias", "")).strip().lower()
        email = str(args.get("email", "")).strip().lower()
        provider = str(args.get("provider", "google")).strip().lower()

        if not email:
            if not alias or alias in ("default", ""):
                return "Error: 'alias' parameter is required for account deletion."
            deleted = self.engine.accounts.delete_account(alias)
            if deleted:
                self.engine._notify_observers("account_updated", {"action": "delete", "alias": alias})
                return f"Successfully removed account alias '{alias}' from accounts.md."
            return f"Account alias '{alias}' was not found in accounts.md."

        assigned_alias = self.engine.accounts.update_account(alias=alias or None, email=email, provider=provider)
        self.engine._notify_observers(
            "account_updated",
            {"action": "upsert", "alias": assigned_alias, "email": email, "provider": provider},
        )
        return f"Successfully saved account '{assigned_alias}' ({email}, provider: {provider}) to accounts.md."

    def _handle_store_fact(
        self,
        args: Dict[str, Any],
        session_id: Optional[str] = None,
        turn_id: Optional[str] = None,
    ) -> str:
        content = str(args.get("content") or args.get("fact") or "").strip()
        if not content:
            return "Error: 'content' (or 'fact') is required for memory_store_fact."

        category = str(args.get("category", "note")).strip().lower()
        if category not in ("project", "system", "conversation", "note"):
            category = "note"

        tags = args.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        self.engine._recent_turn_facts.add(content.lower())

        record = self.engine.storage.store_fact(
            content=content,
            category=category,
            tags=tags,
            source_session_id=session_id,
            source_turn_id=turn_id,
        )
        self.engine._notify_observers(
            "fact_stored",
            {"id": record.id, "category": record.category, "tags": record.tags},
        )
        return f"Stored memory record successfully: [ID: {record.id}, Category: {record.category}]"

    def _handle_search(self, args: Dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' parameter is required for memory_search."

        category = args.get("category")
        if category is not None:
            category = str(category).strip() or None

        top_k_raw = args.get("top_k", args.get("limit", 3))
        try:
            top_k = int(top_k_raw)
        except (ValueError, TypeError):
            top_k = 3

        response = self.engine.storage.search(query=query, category=category, top_k=top_k)
        return response.format_text()

    def _handle_delete(self, args: Dict[str, Any]) -> str:
        mem_id = str(args.get("memory_id", "")).strip()
        if not mem_id:
            return "Error: 'memory_id' is required for memory_delete."

        reason = args.get("reason")
        success = self.engine.storage.delete(memory_id=mem_id, reason=reason)
        if success:
            self.engine._notify_observers("fact_deleted", {"memory_id": mem_id, "reason": reason})
            return f"Deleted memory record '{mem_id}'."
        return f"Memory record '{mem_id}' not found."
