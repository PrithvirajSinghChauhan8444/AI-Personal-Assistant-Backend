import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from modules.adapters.telegram.telegram_adapter import (
    TelegramAdapter,
    split_message,
)


class TestMessageSplitter:
    def test_short_message_not_split(self):
        text = "Hello, world!"
        chunks = split_message(text, max_length=100)
        assert chunks == ["Hello, world!"]

    def test_empty_message(self):
        chunks = split_message("", max_length=100)
        assert chunks == [""]

    def test_long_message_splits_by_newlines(self):
        lines = [f"Line {i} with some content to fill up space." for i in range(20)]
        text = "\n".join(lines)
        chunks = split_message(text, max_length=150)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 150

    def test_code_block_preservation_across_chunks(self):
        text = "Intro text\n```python\nfor i in range(10):\n    print('Hello World ' + str(i))\n```\nOutro text"
        chunks = split_message(text, max_length=60)
        assert len(chunks) >= 2
        # Verify first chunk has closing ``` if inside code block
        if "```python" in chunks[0] and "Outro" not in chunks[0]:
            assert chunks[0].endswith("```")
            assert chunks[1].startswith("```python")


class TestTelegramAdapterAuthAndSessions:
    def test_authorization_whitelist(self):
        adapter = TelegramAdapter(token="fake_token", allowed_user_ids=[12345, 67890])
        assert adapter.is_authorized(12345) is True
        assert adapter.is_authorized(67890) is True
        assert adapter.is_authorized(99999) is False

    def test_empty_whitelist_denies_all(self):
        adapter = TelegramAdapter(token="fake_token", allowed_user_ids=[])
        assert adapter.is_authorized(12345) is False

    def test_session_id_persistence_and_reset(self):
        adapter = TelegramAdapter(token="fake_token", allowed_user_ids=[12345])
        s1 = adapter.get_session_id(1001)
        s2 = adapter.get_session_id(1001)
        assert s1 == s2
        assert s1.startswith("tg_1001_")

        # Another chat has distinct session
        s_other = adapter.get_session_id(1002)
        assert s_other != s1
        assert s_other.startswith("tg_1002_")

        # Reset session
        s3 = adapter.reset_session(1001)
        assert s3 != s1
        assert adapter.get_session_id(1001) == s3


@pytest.mark.asyncio
class TestTelegramAdapterHandlers:
    async def test_unauthorized_user_blocked_on_start(self):
        adapter = TelegramAdapter(token="fake_token", allowed_user_ids=[12345])

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 99999
        mock_update.effective_user = mock_user
        mock_update.effective_message = MagicMock()
        mock_update.effective_message.reply_text = AsyncMock()

        await adapter.handle_start(mock_update, MagicMock())

        mock_update.effective_message.reply_text.assert_called_once()
        args, kwargs = mock_update.effective_message.reply_text.call_args
        assert "Access Denied" in args[0]
        assert "99999" in args[0]

    async def test_authorized_user_accepted_on_start(self):
        adapter = TelegramAdapter(token="fake_token", allowed_user_ids=[12345])

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_user.first_name = "Alice"
        mock_update.effective_user = mock_user
        mock_update.effective_chat.id = 12345
        mock_update.effective_message = MagicMock()
        mock_update.effective_message.reply_text = AsyncMock()

        await adapter.handle_start(mock_update, MagicMock())

        mock_update.effective_message.reply_text.assert_called_once()
        args, _ = mock_update.effective_message.reply_text.call_args
        assert "Welcome, Alice" in args[0]

    async def test_handle_message_runs_orchestrator(self):
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = "The current time is 4:00 PM."

        adapter = TelegramAdapter(
            token="fake_token",
            allowed_user_ids=[12345],
            orchestrator=mock_orchestrator,
        )

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_update.effective_user = mock_user
        mock_update.effective_chat = MagicMock()
        mock_update.effective_chat.id = 999
        mock_update.effective_chat.send_message = AsyncMock()
        mock_update.effective_message.text = "What time is it?"

        mock_status_msg = MagicMock()
        mock_status_msg.edit_text = AsyncMock()
        mock_status_msg.delete = AsyncMock()
        mock_update.effective_message.reply_text = AsyncMock(return_value=mock_status_msg)

        await adapter.handle_message(mock_update, MagicMock())

        mock_orchestrator.run.assert_called_once()
        call_prompt = mock_orchestrator.run.call_args[0][0]
        call_thread = mock_orchestrator.run.call_args[1]["thread_id"]
        assert call_prompt == "What time is it?"
        assert call_thread.startswith("tg_999_")

        mock_status_msg.delete.assert_called_once()
        mock_update.effective_chat.send_message.assert_called_once()
        sent_text = mock_update.effective_chat.send_message.call_args[0][0]
        assert "The current time is 4:00 PM." in sent_text

    async def test_progress_updates_status_message(self):
        def fake_run(prompt, thread_id=None, on_progress=None):
            if on_progress:
                on_progress("📋 Planned 1 subtask via CommunicationWorker...")
                on_progress("⚡ CommunicationWorker finished: Fetched 3 emails...")
            return "Found 3 emails."

        mock_orchestrator = MagicMock()
        mock_orchestrator.run.side_effect = fake_run

        adapter = TelegramAdapter(
            token="fake_token",
            allowed_user_ids=[12345],
            orchestrator=mock_orchestrator,
        )

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_update.effective_user = mock_user
        mock_update.effective_chat = MagicMock()
        mock_update.effective_chat.id = 999
        mock_update.effective_chat.send_message = AsyncMock()
        mock_update.effective_message.text = "Check emails"

        mock_status_msg = MagicMock()
        mock_status_msg.edit_text = AsyncMock()
        mock_status_msg.delete = AsyncMock()
        mock_update.effective_message.reply_text = AsyncMock(return_value=mock_status_msg)

        await adapter.handle_message(mock_update, MagicMock())

        mock_status_msg.delete.assert_called_once()
        mock_update.effective_chat.send_message.assert_called_once()
        assert "Found 3 emails." in mock_update.effective_chat.send_message.call_args[0][0]

    async def test_handle_workers_command(self):
        mock_worker = MagicMock()
        mock_worker.name = "TestWorker"
        mock_worker.categories = ["testing", "system"]

        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = [mock_worker]

        adapter = TelegramAdapter(
            token="fake_token",
            allowed_user_ids=[12345],
            orchestrator=mock_orchestrator,
        )

        mock_update = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_update.effective_user = mock_user
        mock_update.effective_chat = MagicMock()
        mock_update.effective_chat.send_message = AsyncMock()

        await adapter.handle_workers(mock_update, MagicMock())

        mock_update.effective_chat.send_message.assert_called_once()
        sent_text = mock_update.effective_chat.send_message.call_args[0][0]
        assert "TestWorker" in sent_text
        assert "testing, system" in sent_text

    async def test_send_startup_greeting_to_authorized_users(self):
        mock_orchestrator = MagicMock()
        mock_orchestrator.workers = [MagicMock()]

        adapter = TelegramAdapter(
            token="fake_token",
            allowed_user_ids=[12345, 67890],
            orchestrator=mock_orchestrator,
        )

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        await adapter.send_startup_greeting(mock_bot)

        assert mock_bot.send_message.call_count == 2
        calls = mock_bot.send_message.call_args_list
        delivered_ids = {call.kwargs["chat_id"] for call in calls}
        assert delivered_ids == {12345, 67890}
        assert "AI Personal Assistant is Online!" in calls[0].kwargs["text"]
