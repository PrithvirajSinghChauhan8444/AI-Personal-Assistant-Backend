import os
from datetime import datetime
from typing import Any, Dict, List, Optional


class ConversationExporter:
    """
    Exports conversation transcripts in both Clean (Standard) and Verbose (Detailed Execution) formats.
    Supports on-demand terminal printing and file generation.
    """

    @staticmethod
    def format_clean(
        session_id: str,
        turns: List[Any],
        active_source: Optional[str] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Formats a clean, human-readable transcript containing only user queries and assistant responses.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "# 💬 AI Personal Assistant — Conversation Transcript",
            "",
            f"- **Session ID:** `{session_id}`",
            f"- **Exported At:** {now}",
            f"- **Active Source:** {active_source or 'N/A'}",
            f"- **Total Turns:** {len(turns) if turns else (len(chat_history or []) // 2)}",
            "",
            "---",
            "",
        ]

        if turns:
            for turn in turns:
                ts = getattr(turn, "timestamp", "")
                src = (getattr(turn, "source", "unknown") or "unknown").upper()
                prompt = getattr(turn, "user_prompt", "").strip()
                response = getattr(turn, "assistant_response", "").strip()

                time_str = f" — {ts}" if ts else ""
                lines.append(f"### 🧑 User [{src}]{time_str}")
                lines.append(f"{prompt}\n")
                lines.append(f"### 🤖 Assistant{time_str}")
                lines.append(f"{response}\n")
                lines.append("---\n")
        elif chat_history:
            for msg in chat_history:
                role = msg.get("role", "unknown")
                src = (msg.get("source", "unknown") or "unknown").upper()
                content = msg.get("content", "").strip()
                ts = msg.get("timestamp", "")
                time_str = f" — {ts}" if ts else ""

                if role == "user":
                    lines.append(f"### 🧑 User [{src}]{time_str}")
                else:
                    lines.append(f"### 🤖 Assistant{time_str}")
                lines.append(f"{content}\n")
            lines.append("---\n")
        else:
            lines.append("*(No conversation exchanges recorded yet)*\n")

        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def format_verbose(
        session_id: str,
        turns: List[Any],
        active_source: Optional[str] = None,
        registered_workers: Optional[List[str]] = None,
    ) -> str:
        """
        Formats a detailed execution transcript including task decomposition, worker dispatches,
        node transitions, and intermediate results.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        worker_list = ", ".join(registered_workers) if registered_workers else "12 Modular Workers"

        lines = [
            "# 🔬 AI Personal Assistant — Verbose Execution Transcript",
            "",
            f"- **Session ID:** `{session_id}`",
            f"- **Exported At:** {now}",
            f"- **Active Source:** {active_source or 'N/A'}",
            f"- **Total Turns:** {len(turns)}",
            f"- **Workers Active:** {worker_list}",
            "",
            "---",
            "",
        ]

        if not turns:
            lines.append("*(No conversation exchanges recorded yet)*\n")
            return "\n".join(lines).strip() + "\n"

        for idx, turn in enumerate(turns, 1):
            ts = getattr(turn, "timestamp", "")
            src = (getattr(turn, "source", "unknown") or "unknown").upper()
            prompt = getattr(turn, "user_prompt", "").strip()
            response = getattr(turn, "assistant_response", "").strip()
            subtasks = getattr(turn, "subtasks", []) or []
            completed = getattr(turn, "completed_tasks", {}) or {}
            transitions = getattr(turn, "node_transitions", []) or []
            error_logs = getattr(turn, "error_logs", []) or []

            lines.append(f"## 📌 Turn {idx} [{src}] — {ts}")
            lines.append("")
            lines.append(f"### 🎯 Primary Goal\n> {prompt}\n")

            # 1. Planned Subtasks from TaskRouter
            lines.append("### 📋 Task Decomposition (TaskRouter)")
            if subtasks:
                for st in subtasks:
                    st_id = st.get("id", "task")
                    worker = st.get("assigned_worker", "Unassigned")
                    desc = st.get("description", "")
                    conf = st.get("confidence_score", "N/A")
                    reason = st.get("confidence_reason", "")
                    deps = f" (depends on {st.get('depends_on')})" if st.get("depends_on") else ""

                    lines.append(f"- **[{st_id}]** ➔ `{worker}`: {desc}{deps}")
                    if conf != "N/A":
                        lines.append(f"  • *Confidence:* `{conf}` ({reason})")
            else:
                lines.append("- *Direct execution / No subtasks generated*")
            lines.append("")

            # 2. Worker Executions & Outputs
            lines.append("### ⚡ Worker Executions & Completed Tasks")
            if completed:
                for tid, cdata in completed.items():
                    c_worker = cdata.get("worker", "Worker")
                    c_desc = cdata.get("description", tid)
                    c_summary = cdata.get("summary", "")
                    c_status = cdata.get("status", "completed")

                    lines.append(f"- **{c_worker}** (`{tid}`): *{c_status.upper()}*")
                    lines.append(f"  • *Action:* {c_desc}")
                    if c_summary:
                        lines.append(f"  • *Output:* {c_summary}")
            else:
                lines.append("- *No worker task summaries recorded*")
            lines.append("")

            # 3. Node Transitions / Trace
            if transitions:
                lines.append("### 🔄 Node Transition Sequence")
                for step_num, tr in enumerate(transitions, 1):
                    node = tr.get("node", "UnknownNode")
                    nxt = tr.get("next_node", "")
                    route_info = f" ➔ Route to: `{nxt}`" if nxt else ""
                    lines.append(f"{step_num}. `{node}`{route_info}")
                lines.append("")

            # 4. Error Logs if any
            if error_logs:
                lines.append("### ⚠️ Recorded Errors / Warnings")
                for err in error_logs:
                    lines.append(f"- ❌ `{err}`")
                lines.append("")

            # 5. Synthesized Final Answer
            lines.append("### ✨ Final Synthesized Answer")
            lines.append(f"{response}\n")
            lines.append("---\n")

        return "\n".join(lines).strip() + "\n"

    @classmethod
    def save_to_file(
        cls,
        content: str,
        session_id: str,
        verbose: bool = False,
        export_dir: Optional[str] = None,
    ) -> str:
        """
        Saves the formatted transcript string to a file and returns the absolute path.
        """
        if not export_dir:
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )
            export_dir = os.path.join(project_root, "Memory", "exports")

        os.makedirs(export_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode = "verbose" if verbose else "clean"
        safe_session = session_id.replace(":", "_").replace("/", "_")
        filename = f"conversation_{safe_session}_{mode}_{timestamp}.md"
        file_path = os.path.join(export_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return os.path.abspath(file_path)
