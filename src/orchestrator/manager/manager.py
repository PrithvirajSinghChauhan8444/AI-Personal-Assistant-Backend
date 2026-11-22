"""Layer 2 Orchestrator - Manager Agent (Cognitive Planner).

The Manager Agent is the solitary agent residing in Layer 2 (Orchestrator).
It possesses NO leaf tools (no shell execution, no filesystem manipulation, no browser actions).
Its sole purpose is cognitive reasoning, goal decomposition, and constructing an actionable
TaskPlan Directed Acyclic Graph (DAG) for downstream specialist workers.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path for direct module execution
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load environment variables if available
try:
    from dotenv import load_dotenv

    if (_PROJECT_ROOT / ".env").is_file():
        load_dotenv(_PROJECT_ROOT / ".env")
    elif (_PROJECT_ROOT / "config" / ".env").is_file():
        load_dotenv(_PROJECT_ROOT / "config" / ".env")
except ImportError:
    pass

from src.agents.manifest import find_agent_config
from src.models.factory import ModelFactory

DEFAULT_WORKER_SPECS = [
    {
        "name": "system",
        "description": "Local Linux OS operations: file reading/writing/deletion, shell execution, process monitoring, and git version control.",
        "routing_rules": [
            "Assign when inspecting local files, directory trees, terminal scripts, or git repositories."
        ],
    },
    {
        "name": "browser",
        "description": "Interactive web browser automation: navigating URLs, clicking elements, reading dynamic web pages, and taking screenshots via Playwright.",
        "routing_rules": [
            "Assign when a task requires rendering modern JavaScript websites, logging into web dashboards, or visual UI verification."
        ],
    },
    {
        "name": "research",
        "description": "Deep research, web searching, summarizing articles/papers, fact-checking, and long-term memory retrieval.",
        "routing_rules": [
            "Assign when looking up public facts, searching the web, or synthesizing multiple information sources."
        ],
    },
    {
        "name": "productivity",
        "description": "Personal communication, scheduling, and coursework: searching and reading Gmail, creating/updating Google Calendar events, and inspecting Google Classroom courses, assignments, and announcements.",
        "routing_rules": [
            "Assign for all email (Gmail) inquiries, calendar events, meeting scheduling, personal agendas, and Google Classroom coursework or announcements."
        ],
    },
    {
        "name": "memory",
        "description": "Personal memory curation and recall: managing core user identity, preferences, rules, and searching/storing long-term episodic facts.",
        "routing_rules": [
            "Assign when the user asks to recall personal preferences, update user rules/profile, remember specific facts, or delete outdated memories."
        ],
    },
]


class ManagerAgent:
    """Sole cognitive planning agent of Layer 2 Orchestrator.

    Decomposes user prompts into DAG subtasks assigned strictly to known specialist workers.
    """

    def __init__(
        self,
        config_path: str = "config/agents.json",
        prompt_path: str = "src/orchestrator/manager/prompt.md",
        model_override: Optional[str] = None,
        temperature_override: Optional[float] = None,
    ) -> None:
        self.config_path = config_path
        self.prompt_path = prompt_path

        # Load user configuration and auto-discover enabled specialist workers
        self.all_agents_config = self._load_all_agents_config()
        self.agent_config = self.all_agents_config.get("manager", {})
        self.workers = self._discover_and_filter_workers()

        self.model_id = model_override or self.agent_config.get("model", "google:gemini-3.5-flash-lite")
        self.temperature = (
            temperature_override
            if temperature_override is not None
            else float(self.agent_config.get("temperature", 0.1))
        )

        self._system_prompt = self._build_system_prompt()

    def _load_all_agents_config(self) -> Dict[str, Any]:
        """Loads complete agents.json configuration."""
        candidate_paths = [
            Path(self.config_path),
            _PROJECT_ROOT / "config" / "agents.json",
            Path("config/agents.json"),
        ]
        for p in candidate_paths:
            if p.is_file():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as err:
                    sys.stderr.write(f"[ManagerAgent] Warning: could not parse {p}: {err}\n")
        return {}

    def _discover_and_filter_workers(self) -> List[Dict[str, Any]]:
        """Auto-discovers workers from agents directory and filters by user configuration."""
        discovered: Dict[str, Dict[str, Any]] = {}

        # 1. Base defaults as initial fallback
        for spec in DEFAULT_WORKER_SPECS:
            name = spec["name"].lower()
            discovered[name] = dict(spec)

        # 2. Auto-discovery from src/agents/ folders
        agents_dir = _PROJECT_ROOT / "src" / "agents"
        if agents_dir.is_dir():
            for child in agents_dir.iterdir():
                if not child.is_dir() or child.name.startswith((".", "_")) or child.name in ("manager", "engine"):
                    continue

                worker_name = child.name.lower()
                manifest_file = find_agent_config(child, child.name)
                if not manifest_file or not manifest_file.is_file():
                    continue

                if worker_name not in discovered:
                    discovered[worker_name] = {
                        "name": worker_name,
                        "description": f"Specialist worker in {worker_name}.",
                        "routing_rules": [f"Assign for tasks relating to {worker_name}."],
                    }

                try:
                    with open(manifest_file, "r", encoding="utf-8") as mf:
                        mdata = json.load(mf)
                        if "description" in mdata:
                            discovered[worker_name]["description"] = mdata["description"]
                        if "routing_rules" in mdata:
                            discovered[worker_name]["routing_rules"] = mdata["routing_rules"]
                        if "fallback_capability" in mdata:
                            discovered[worker_name]["fallback"] = mdata["fallback_capability"]
                except Exception:
                    pass

        # 3. Apply user configuration from config/agents.json
        for name, cfg in self.all_agents_config.items():
            name_lower = name.lower()
            if name_lower == "manager":
                continue

            # If user explicitly disabled the agent, delete from discovered
            if not cfg.get("enabled", True):
                if name_lower in discovered:
                    del discovered[name_lower]
                continue

            # Load explicit config_path / manifest_path if provided
            manifest_path = cfg.get("config_path") or cfg.get("manifest_path")
            if manifest_path:
                mp = _PROJECT_ROOT / manifest_path if not Path(manifest_path).is_absolute() else Path(manifest_path)
                if mp.is_file():
                    try:
                        with open(mp, "r", encoding="utf-8") as mf:
                            mdata = json.load(mf)
                            target_key = mdata.get("agent_identifier", name_lower).lower()
                            if target_key not in discovered:
                                discovered[target_key] = {"name": target_key}
                            if "description" in mdata:
                                discovered[target_key]["description"] = mdata["description"]
                            if "routing_rules" in mdata:
                                discovered[target_key]["routing_rules"] = mdata["routing_rules"]
                            if "fallback_capability" in mdata:
                                discovered[target_key]["fallback"] = mdata["fallback_capability"]
                    except Exception:
                        pass

            # Merge user config overrides
            if name_lower not in discovered:
                discovered[name_lower] = {
                    "name": name_lower,
                    "description": cfg.get("description", f"Specialist worker in {name_lower}."),
                    "routing_rules": cfg.get("routing_rules", [f"Assign for {name_lower} operations."]),
                }
            else:
                if "description" in cfg:
                    discovered[name_lower]["description"] = cfg["description"]
                if "routing_rules" in cfg:
                    discovered[name_lower]["routing_rules"] = cfg["routing_rules"]

        # 4. Return strictly active, enabled workers
        active_workers: List[Dict[str, Any]] = []
        for name, spec in discovered.items():
            user_setting = self.all_agents_config.get(name, {})
            if isinstance(user_setting, dict) and user_setting.get("enabled") is True:
                active_workers.append(spec)

        return active_workers

    def _build_system_prompt(self) -> str:
        """Loads the markdown prompt template and formats worker capabilities."""
        candidates = [
            Path(self.prompt_path),
            Path(__file__).resolve().parent / "prompt.md",
            _PROJECT_ROOT / "src" / "orchestrator" / "manager" / "prompt.md",
            _PROJECT_ROOT / "src" / "orchestrator" / "planner" / "manager_prompt.md",
            Path("src/orchestrator/manager/prompt.md"),
            Path("src/orchestrator/planner/manager_prompt.md"),
            _PROJECT_ROOT / "config" / "prompts" / "manager_prompt.md",
            Path("config/prompts/manager_prompt.md"),
        ]
        template = ""
        for p in candidates:
            if p.is_file():
                try:
                    template = p.read_text(encoding="utf-8")
                    break
                except Exception:
                    pass

        if not template:
            template = (
                "You are the Task Router and Manager Agent. "
                "Decompose user requests into structured subtasks.\n"
                "Available workers:\n{{AVAILABLE_WORKERS}}\n\n"
                "Respond strictly with raw JSON matching the schema."
            )

        worker_bullets: List[str] = []
        for w in self.workers:
            if w.get("name", "").lower() == "summarizer":
                # Summarizer is a terminal gateway pipeline agent, never scheduled by manager
                continue
            worker_bullets.append(f"- {w['name']}: {w['description']}")
            for r in w.get("routing_rules", []):
                worker_bullets.append(f"  • {r}")
            if w.get("fallback"):
                worker_bullets.append(f"  • Fallback agent: {w['fallback']}")

        # Inject workspace and artifacts paths from system.json
        try:
            from src.agents.factory import load_system_config
            sys_cfg = load_system_config()
            ws_dir = sys_cfg.get("workspace_dir", "workspace")
            art_dir = sys_cfg.get("artifacts_dir", "workspace/artifacts")
        except Exception:
            ws_dir = "workspace"
            art_dir = "workspace/artifacts"

        formatted = template.replace("{{AVAILABLE_WORKERS}}", "\n".join(worker_bullets))
        formatted = formatted.replace("{{WORKSPACE_DIR}}", ws_dir)
        formatted = formatted.replace("{{ARTIFACTS_DIR}}", art_dir)
        return formatted

    def _load_core_profile(self) -> str:
        """Loads User Core Profile from memory layer dynamically on every turn."""
        try:
            from src.memory.engine import resolve_memory_base_dir
            base_dir = resolve_memory_base_dir()
            profile_path = Path(base_dir) / "core_profile.md"
            if profile_path.is_file():
                content = profile_path.read_text(encoding="utf-8").strip()
                if content:
                    return content
        except Exception:
            pass

        # Fallback candidate locations
        candidates = [
            Path.home() / ".config" / "ai-assistant" / "memory" / "core_profile.md",
            _PROJECT_ROOT / "workspace" / "Memory" / "core_profile.md",
            _PROJECT_ROOT / "Memory" / "core_profile.md",
        ]
        for c in candidates:
            if c.is_file():
                try:
                    content = c.read_text(encoding="utf-8").strip()
                    if content:
                        return content
                except Exception:
                    pass
        return ""

    def _load_active_terminal_sessions(self) -> str:
        """Discovers active persistent terminal sessions from tmux."""
        try:
            import subprocess
            res = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}\t#{session_attached}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode != 0 or not res.stdout.strip():
                return ""
            lines = [f"- `{line.split('\t')[0]}`" for line in res.stdout.strip().splitlines() if line.strip()]
            if lines:
                return "Active Terminal Sessions on Host:\n" + "\n".join(lines) + "\n(Note: Prefer routing tasks to existing sessions where appropriate)"
        except Exception:
            pass
        return ""

    async def plan(
        self,
        goal: str,
        context_data: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Asynchronously decomposes the goal into a validated TaskPlan DAG."""
        goal = (goal or "").strip()
        if not goal:
            raise ValueError("cannot plan with an empty goal")

        if not self.workers:
            raise ValueError("Cannot plan tasks: no specialist worker agents are currently enabled in config/agents.json. Please enable the required workers in config/agents.json to proceed.")

        context_parts = []

        # Dynamically inject User Core Profile & Requirements on every turn
        core_profile = self._load_core_profile()
        if core_profile:
            context_parts.append(f"User Core Profile & Requirements:\n{core_profile}")

        # Dynamically inject live active terminal sessions on host
        active_sessions = self._load_active_terminal_sessions()
        if active_sessions:
            context_parts.append(active_sessions)

        if conversation_history:
            history_str = "\n".join(
                f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in conversation_history
            )
            context_parts.append(f"Conversation History:\n{history_str}")
        if context_data:
            context_parts.append(f"Context: {json.dumps(context_data)}")

        user_content = f"User Request: {goal}"
        if context_parts:
            user_content = f"{'\n\n'.join(context_parts)}\n\n{user_content}"

        client = ModelFactory.get_client(
            model_id=self.model_id,
            temperature=self.temperature,
        )
        raw_output = await client.generate(
            system_prompt=self._system_prompt,
            user_prompt=user_content,
        )
        parsed_plan = self._extract_and_validate_json(raw_output, goal)
        return parsed_plan

    def plan_sync(
        self,
        goal: str,
        context_data: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for plan()."""
        return asyncio.run(self.plan(goal, context_data, conversation_history))

    def _extract_and_validate_json(self, raw_text: str, original_goal: str) -> Dict[str, Any]:
        """Strips markdown fences and parses raw JSON plan conforming to schema."""
        cleaned = raw_text.strip()

        # Remove markdown code blocks if the model included them
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 2:
                lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

        # Find first '{' and last '}'
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

        plan = json.loads(cleaned)
        return self._normalize_plan(plan, original_goal)

    def _normalize_plan(self, plan: Dict[str, Any], original_goal: str) -> Dict[str, Any]:
        """Normalizes and validates fields against the expected TaskPlan schema."""
        plan_id = plan.get("plan_id") or f"plan_{uuid.uuid4().hex[:12]}"
        primary_goal = plan.get("primary_goal") or original_goal
        raw_tasks = plan.get("subtasks") or []

        valid_workers = {w["name"].lower() for w in self.workers}
        if not raw_tasks:
            lower_goal = original_goal.lower().strip()
            greetings = {"hi", "hello", "hey", "hola", "howdy", "sup", "yo", "good morning", "good evening", "good afternoon", "ho", ".", "test"}
            is_greeting = lower_goal in greetings or len(lower_goal) <= 3 or "greet" in primary_goal.lower()
            if is_greeting and "system" in valid_workers:
                raw_tasks = [{
                    "id": "task_1",
                    "description": f"Respond to user message: {original_goal}",
                    "assigned_worker": "system",
                    "depends_on": [],
                    "confidence_score": 1.0,
                    "confidence_reason": "Conversational greeting fallback",
                }]
            else:
                raise ValueError("No subtasks could be scheduled: required capabilities are disabled or missing from enabled workers in config/agents.json.")

        normalized_tasks: List[Dict[str, Any]] = []

        for idx, t in enumerate(raw_tasks, start=1):
            task_id = str(t.get("id") or f"task_{idx}")
            desc = str(t.get("description") or original_goal)

            worker = str(t.get("assigned_worker") or t.get("assigned_agent") or "").lower().strip()
            if not worker or worker not in valid_workers:
                raise ValueError(f"Task '{task_id}' cannot be scheduled: worker '{worker}' is disabled or not found in config/agents.json.")

            deps = t.get("depends_on")
            if not isinstance(deps, list):
                deps = []
            deps = [str(d) for d in deps]

            try:
                conf = float(t.get("confidence_score", 1.0))
            except (ValueError, TypeError):
                conf = 1.0
            conf = max(0.0, min(1.0, conf))

            normalized_tasks.append({
                "id": task_id,
                "description": desc,
                "assigned_worker": worker,
                "assigned_agent": worker,
                "depends_on": deps,
                "confidence_score": conf,
                "confidence_reason": str(t.get("confidence_reason") or "Direct plan generation"),
                "entity_reference": t.get("entity_reference"),
                "status": "pending",
            })

        return {
            "plan_id": plan_id,
            "primary_goal": primary_goal,
            "subtasks": normalized_tasks,
        }


def main() -> None:
    """CLI and subprocess entry point for Go and external callers."""
    import argparse

    parser = argparse.ArgumentParser(description="Layer 2 Manager Cognitive Planner")
    parser.add_argument("--goal", type=str, help="Primary user goal to decompose into a TaskPlan DAG")
    parser.add_argument("--context", type=str, default="", help="JSON string of contextual metadata")
    parser.add_argument("--model", type=str, default=None, help="Model override (e.g. google:gemini-3.5-flash-lite)")
    parser.add_argument("--temperature", type=float, default=None, help="Sampling temperature")
    parser.add_argument("--raw-llm", action="store_true", help="Raw LLM generation mode")
    parser.add_argument("--system", type=str, default="", help="System prompt in raw LLM mode")
    parser.add_argument("--user", type=str, default="", help="User prompt in raw LLM mode")

    args = parser.parse_args()

    if args.raw_llm:
        sys_prompt = args.system
        usr_prompt = args.user
        if not usr_prompt and not sys.stdin.isatty():
            try:
                stdin_data = json.load(sys.stdin)
                sys_prompt = stdin_data.get("system", sys_prompt)
                usr_prompt = stdin_data.get("user", usr_prompt)
            except Exception:
                pass

        async def run_raw() -> None:
            client = ModelFactory.get_client(model_id=args.model, temperature=args.temperature or 0.0)
            res = await client.generate(system_prompt=sys_prompt, user_prompt=usr_prompt)
            sys.stdout.write(res)
            sys.stdout.flush()

        asyncio.run(run_raw())
        return

    goal = args.goal
    ctx_data: Optional[Dict[str, Any]] = None
    conv_history: Optional[List[Dict[str, Any]]] = None

    if not goal and not sys.stdin.isatty():
        try:
            stdin_data = json.load(sys.stdin)
            goal = stdin_data.get("goal") or stdin_data.get("prompt")
            ctx_data = stdin_data.get("context")
            conv_history = stdin_data.get("history") or stdin_data.get("conversation_history")
        except Exception as err:
            sys.stderr.write(f"[Manager] Failed to read JSON from stdin: {err}\n")

    if not goal:
        sys.stderr.write("Error: --goal or stdin JSON containing 'goal' is required.\n")
        sys.exit(1)

    if args.context and not ctx_data:
        try:
            ctx_data = json.loads(args.context)
        except Exception:
            pass

    manager = ManagerAgent(
        model_override=args.model,
        temperature_override=args.temperature,
    )
    result = manager.plan_sync(
        goal=goal,
        context_data=ctx_data,
        conversation_history=conv_history,
    )

    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()

