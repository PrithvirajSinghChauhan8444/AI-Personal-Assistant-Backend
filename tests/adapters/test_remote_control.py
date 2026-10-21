import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from modules.adapters.remote_control.coordinator import (
    ConversationTurn,
    RemoteControlCoordinator,
)
from modules.adapters.remote_control.exporter import ConversationExporter
from modules.adapters.telegram.telegram_adapter import TelegramAdapter


class TestConversationExporter:
    def test_format_clean_empty(self):
        content = ConversationExporter.format_clean("test_session", turns=[], chat_history=[])
        assert "test_session" in content
        assert "No conversation exchanges recorded" in content

    def test_format_clean_with_turns(self):
        turn1 = ConversationTurn(
            turn_id=1,
            source="cli",
            user_prompt="Hello assistant",
            assistant_response="Hello user",
            timestamp="2026-10-20T12:00:00",
        )
        turn2 = ConversationTurn(
            turn_id=2,
            source="telegram",
            user_prompt="Check my calendar",
            assistant_response="You have 1 meeting",
            timestamp="2026-10-20T12:05:00",
        )
        content = ConversationExporter.format_clean("test_session", turns=[turn1, turn2])
        assert "Session ID:** `test_session`" in content
        assert "Total Turns:** 2" in content
        assert "🧑 User [CLI]" in content
        assert "Hello assistant" in content
        assert "🤖 Assistant" in content
        assert "🧑 User [TELEGRAM]" in content
        assert "Check my calendar" in content
        assert "You have 1 meeting" in content

    def test_format_verbose(self):
        turn = ConversationTurn(
            turn_id=1,
            source="telegram",
            user_prompt="Decompose and execute",
            assistant_response="Final synthesized answer",
            timestamp="2026-10-20T12:00:00",
            subtasks=[
                {
                    "id": "task_1",
                    "description": "Fetch metrics",
                    "assigned_worker": "SystemWorker",
                    "confidence_score": 0.95,
                    "confidence_reason": "Direct system metrics match",
                }
            ],
            completed_tasks={
                "task_1": {
                    "worker": "SystemWorker",
                    "description": "Fetch metrics",
                    "summary": "CPU: 10%, RAM: 30%",
                    "status": "completed",
                }
            },
            node_transitions=[
                {"node": "TaskRouter", "next_node": "SystemWorker"},
                {"node": "SystemWorker", "next_node": "OutputFinalizer"},
            ],
        )

        content = ConversationExporter.format_verbose("test_session", turns=[turn])
        assert "Verbose Execution Transcript" in content
        assert "Turn 1 [TELEGRAM]" in content
        assert "Task Decomposition (TaskRouter)" in content
        assert "SystemWorker" in content
        assert "CPU: 10%, RAM: 30%" in content
        assert "Node Transition Sequence" in content
        assert "Final Synthesized Answer" in content

    def test_save_to_file(self, tmp_path):
        content = "# Test Conversation Transcript\nHello World"
        file_path = ConversationExporter.save_to_file(
            content=content,
            session_id="session_xyz",
            verbose=False,
            export_dir=str(tmp_path),
        )
        assert os.path.exists(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            saved_content = f.read()
        assert "Hello World" in saved_content
        assert "session_xyz" in file_path
        assert "clean" in file_path


class TestRemoteControlCoordinator:
    def test_active_source_shifting(self):
        """Rule 1: Only when user queries from the other source does conversation shift."""
        mock_orch = MagicMock()
        mock_orch.run.return_value = "Mock response"
        mock_orch.get_pipeline_state.return_value = {
            "active_subtasks": [],
            "working_memory": {"test_key": "val1"},
            "completed_tasks": {},
        }

        coordinator = RemoteControlCoordinator(orchestrator=mock_orch, session_id="test_remote_1")
        assert coordinator.active_source is None

        shifts = []
        coordinator.register_shift_listener(lambda old_s, new_s: shifts.append((old_s, new_s)))

        # Query 1 from CLI
        resp1 = coordinator.execute_query("CLI query 1", source="cli")
        assert resp1 == "Mock response"
        assert coordinator.active_source == "cli"
        assert len(shifts) == 1
        assert shifts[-1] == ("NONE", "cli")

        # Query 2 from CLI again -> No shift
        coordinator.execute_query("CLI query 2", source="cli")
        assert coordinator.active_source == "cli"
        assert len(shifts) == 1  # Still 1, didn't shift

        # Query 3 from Telegram -> Shifts to Telegram
        resp3 = coordinator.execute_query("Telegram query 1", source="telegram")
        assert resp3 == "Mock response"
        assert coordinator.active_source == "telegram"
        assert len(shifts) == 2
        assert shifts[-1] == ("cli", "telegram")

        # Query 4 from CLI -> Shifts back to CLI
        coordinator.execute_query("CLI query 3", source="cli")
        assert coordinator.active_source == "cli"
        assert len(shifts) == 3
        assert shifts[-1] == ("telegram", "cli")

    def test_shared_context_preservation(self):
        """Verify CLI and Telegram operate over the exact same session state and history."""
        mock_orch = MagicMock()
        mock_orch.run.side_effect = [
            "CLI response 1",
            "Telegram response 2",
        ]
        mock_orch.get_pipeline_state.side_effect = [
            {"working_memory": {"cli_data": "recorded"}, "completed_tasks": {"task_1": {"summary": "done"}}},
            {"working_memory": {"tg_data": "updated"}, "completed_tasks": {"task_2": {"summary": "done2"}}},
        ]

        coordinator = RemoteControlCoordinator(orchestrator=mock_orch, session_id="shared_thread_99")

        # 1. Query from CLI
        coordinator.execute_query("Set meeting tomorrow", source="cli")
        assert len(coordinator.turns) == 1
        assert len(coordinator.chat_history) == 2  # user + assistant
        assert coordinator.working_memory.get("cli_data") == "recorded"

        # 2. Query from Telegram in SAME session
        coordinator.execute_query("What meeting did I set?", source="telegram")
        assert len(coordinator.turns) == 2
        assert len(coordinator.chat_history) == 4
        assert coordinator.working_memory.get("tg_data") == "updated"

        # Ensure orchestrator.run was called with shared chat history
        second_call_history = mock_orch.run.call_args_list[1].kwargs["chat_history"]
        assert len(second_call_history) == 2  # Has previous CLI turn!
        assert second_call_history[0]["content"] == "Set meeting tomorrow"
        assert second_call_history[0]["source"] == "cli"

    def test_on_demand_export_file(self, tmp_path):
        """Rule 2: On-demand export with clean and verbose options."""
        mock_orch = MagicMock()
        mock_orch.run.return_value = "Done task"
        mock_orch.get_pipeline_state.return_value = {
            "active_subtasks": [{"id": "t1", "description": "test subtask", "assigned_worker": "SystemWorker"}],
            "working_memory": {},
            "completed_tasks": {"t1": {"worker": "SystemWorker", "description": "test", "summary": "Metrics 100%"}},
        }

        coordinator = RemoteControlCoordinator(orchestrator=mock_orch, session_id="test_export_sess")
        coordinator.execute_query("Run metrics check", source="cli")

        # Clean export
        clean_file = coordinator.export_conversation_to_file(verbose=False, export_dir=str(tmp_path))
        assert os.path.exists(clean_file)
        with open(clean_file, "r", encoding="utf-8") as f:
            clean_text = f.read()
        assert "Run metrics check" in clean_text
        assert "Done task" in clean_text

        # Verbose export
        verbose_file = coordinator.export_conversation_to_file(verbose=True, export_dir=str(tmp_path))
        assert os.path.exists(verbose_file)
        with open(verbose_file, "r", encoding="utf-8") as f:
            verbose_text = f.read()
        assert "Verbose Execution Transcript" in verbose_text
        assert "Task Decomposition" in verbose_text
        assert "SystemWorker" in verbose_text


@pytest.mark.asyncio
class TestTelegramRemoteControlIntegration:
    async def test_telegram_adapter_uses_coordinator(self):
        mock_coord = MagicMock()
        mock_coord.session_id = "remote_shared_123"
        mock_coord.execute_query.return_value = "Answer via coordinator"

        adapter = TelegramAdapter(
            token="fake_token",
            allowed_user_ids=[12345],
            coordinator=mock_coord,
        )

        assert adapter.get_session_id(999) == "remote_shared_123"

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_update.effective_user = mock_user
        mock_update.effective_chat = MagicMock()
        mock_update.effective_chat.id = 999
        mock_update.effective_chat.send_message = AsyncMock()
        mock_update.effective_message.text = "Hello via Telegram"

        mock_status_msg = MagicMock()
        mock_status_msg.edit_text = AsyncMock()
        mock_status_msg.delete = AsyncMock()
        mock_update.effective_message.reply_text = AsyncMock(return_value=mock_status_msg)

        await adapter.handle_message(mock_update, MagicMock())

        mock_coord.execute_query.assert_called_once()
        assert mock_coord.execute_query.call_args[0][0] == "Hello via Telegram"
        assert mock_coord.execute_query.call_args[1]["source"] == "telegram"
        mock_update.effective_chat.send_message.assert_called_once()
        assert "Answer via coordinator" in mock_update.effective_chat.send_message.call_args[0][0]

    async def test_telegram_export_command_sends_document(self, tmp_path):
        """Rule 2: Telegram /export sends document file."""
        mock_coord = MagicMock()
        mock_coord.session_id = "remote_shared_456"
        mock_coord.turns = [MagicMock()]
        mock_coord.chat_history = [{"role": "user", "content": "hi"}]

        # Create real dummy file for sending
        export_file = tmp_path / "conversation_export.md"
        export_file.write_text("# Exported Content")
        mock_coord.export_conversation_to_file.return_value = str(export_file)

        adapter = TelegramAdapter(
            token="fake_token",
            allowed_user_ids=[12345],
            coordinator=mock_coord,
        )

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_update.effective_user = mock_user
        mock_update.effective_chat.id = 12345
        mock_update.effective_message = MagicMock()
        mock_update.effective_message.reply_document = AsyncMock()

        mock_context = MagicMock()
        mock_context.args = []

        await adapter.handle_export(mock_update, mock_context)

        mock_coord.export_conversation_to_file.assert_called_once_with(verbose=False)
        mock_update.effective_message.reply_document.assert_called_once()
        kwargs = mock_update.effective_message.reply_document.call_args.kwargs
        assert "document" in kwargs
        assert "remote_shared_456" in kwargs["caption"]

    async def test_telegram_export_verbose_command(self, tmp_path):
        """Rule 2: Telegram /export_verbose sends verbose document file."""
        mock_coord = MagicMock()
        mock_coord.session_id = "remote_shared_789"
        mock_coord.turns = [MagicMock()]
        mock_coord.chat_history = [{"role": "user", "content": "hi"}]

        export_file = tmp_path / "conversation_verbose.md"
        export_file.write_text("# Verbose Export")
        mock_coord.export_conversation_to_file.return_value = str(export_file)

        adapter = TelegramAdapter(
            token="fake_token",
            allowed_user_ids=[12345],
            coordinator=mock_coord,
        )

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_update.effective_user = mock_user
        mock_update.effective_chat.id = 12345
        mock_update.effective_message = MagicMock()
        mock_update.effective_message.reply_document = AsyncMock()

        await adapter.handle_export_verbose(mock_update, MagicMock())

        mock_coord.export_conversation_to_file.assert_called_once_with(verbose=True)
        mock_update.effective_message.reply_document.assert_called_once()
        kwargs = mock_update.effective_message.reply_document.call_args.kwargs
        assert "Detailed Verbose" in kwargs["caption"]

    async def test_telegram_status_command_shows_remote_control(self):
        mock_coord = MagicMock()
        mock_coord.session_id = "remote_sess_abc"
        mock_coord.active_source = "cli"
        mock_coord.turns = [1, 2, 3]

        mock_orch = MagicMock()
        mock_orch.workers = []

        adapter = TelegramAdapter(
            token="fake_token",
            allowed_user_ids=[12345],
            orchestrator=mock_orch,
            coordinator=mock_coord,
        )

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_update.effective_user = mock_user
        mock_update.effective_chat = MagicMock()
        mock_update.effective_chat.id = 12345
        mock_update.effective_chat.send_message = AsyncMock()

        await adapter.handle_status(mock_update, MagicMock())

        mock_update.effective_chat.send_message.assert_called_once()
        msg = mock_update.effective_chat.send_message.call_args[0][0]
        assert "Remote Control (CLI + Telegram)" in msg
        assert "CLI" in msg
        assert "remote_sess_abc" in msg
        assert "Total Turns:</b> <code>3</code>" in msg


class TestModularRemoteCommand:
    def test_handle_remote_command_mid_session_activation(self):
        from run_modular import handle_remote_command

        mock_orch = MagicMock()
        mock_orch.workers = []
        session_id = "test_cli_sess_1"
        chat_history = [{"role": "user", "content": "Prior message"}]
        working_memory = {"key1": "val1"}
        completed_tasks = {}

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "1234:fake_token", "TELEGRAM_ALLOWED_USER_IDS": "111,222"}):
            with patch("modules.adapters.telegram.telegram_adapter.TelegramAdapter.start_background") as mock_start:
                coordinator = handle_remote_command(
                    coordinator=None,
                    orchestrator=mock_orch,
                    session_id=session_id,
                    chat_history=chat_history,
                    working_memory=working_memory,
                    completed_tasks=completed_tasks,
                    cmd_args="start",
                )

                assert coordinator is not None
                assert coordinator.session_id == session_id
                assert len(coordinator.chat_history) == 1
                assert coordinator.chat_history[0]["content"] == "Prior message"
                mock_start.assert_called_once()

    def test_handle_remote_command_stop(self):
        from run_modular import handle_remote_command

        mock_coord = MagicMock()
        result = handle_remote_command(
            coordinator=mock_coord,
            orchestrator=MagicMock(),
            session_id="sess",
            chat_history=[],
            working_memory={},
            completed_tasks={},
            cmd_args="stop",
        )
        assert result is None
        mock_coord.stop.assert_called_once()

    def test_telegram_service_flag_starts_service(self):
        import run_modular

        with patch.object(sys, "argv", ["run_modular.py", "--telegram-service"]):
            with patch("run_modular.start_telegram_service") as mock_service:
                run_modular.main()
                mock_service.assert_called_once_with(daemon=False)

    def test_telegram_service_flag_short_alias(self):
        import run_modular

        with patch.object(sys, "argv", ["run_modular.py", "-t"]):
            with patch("run_modular.start_telegram_service") as mock_service:
                run_modular.main()
                mock_service.assert_called_once_with(daemon=False)

    def test_telegram_service_daemon_flag(self):
        import run_modular

        with patch.object(sys, "argv", ["run_modular.py", "--telegram", "--daemon"]):
            with patch("run_modular.start_telegram_service") as mock_service:
                run_modular.main()
                mock_service.assert_called_once_with(daemon=True)

    def test_start_telegram_service_calls_run_telegram(self):
        from run_modular import start_telegram_service

        with patch("run_telegram.main") as mock_tg_main:
            start_telegram_service(daemon=False)
            mock_tg_main.assert_called_once()


