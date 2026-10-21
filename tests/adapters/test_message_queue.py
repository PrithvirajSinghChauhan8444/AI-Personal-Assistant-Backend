import asyncio
import os
import sys
import pytest
from unittest.mock import AsyncMock

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from modules.adapters.telegram.message_queue import (
    OutboundMessageQueue,
    format_failure_message,
    is_quota_or_rate_limit_error,
)


class TestMessageQueueAndFailures:
    def test_quota_error_detection(self):
        assert is_quota_or_rate_limit_error("Resource has been exhausted (Google 429)") is True
        assert is_quota_or_rate_limit_error("429 Too Many Requests") is True
        assert is_quota_or_rate_limit_error("RateLimitError: quota exceeded") is True
        assert is_quota_or_rate_limit_error("Database connection timeout") is False

    def test_format_failure_message_quota(self):
        msg = format_failure_message("ResourceExhausted: 429 Quota exceeded")
        assert "API Quota / Rate Limit Exceeded" in msg
        assert "MODEL_PROVIDER=groq" in msg
        assert "MODEL_PROVIDER=ollama" in msg

    def test_format_failure_message_general(self):
        msg = format_failure_message("FileNotFoundError: missing config.json")
        assert "Execution Failure Encountered" in msg
        assert "FileNotFoundError" in msg

    @pytest.mark.asyncio
    async def test_queue_batches_rapid_messages_for_same_chat(self):
        sent_messages = []

        async def mock_send(chat_id, text, parse_mode):
            sent_messages.append((chat_id, text))

        queue = OutboundMessageQueue(
            send_fn=mock_send,
            batch_window_seconds=0.1,
            send_interval_seconds=0.05,
        )
        queue.start()

        # Enqueue 3 messages quickly for chat 123
        queue.enqueue(123, "Message A")
        queue.enqueue(123, "Message B")
        queue.enqueue(123, "Message C")

        # Allow queue loop to process batch
        await asyncio.sleep(0.35)
        await queue.stop()

        # Should be batched together into 1 combined delivery!
        assert len(sent_messages) == 1
        chat_id, delivered_text = sent_messages[0]
        assert chat_id == 123
        assert "Message A" in delivered_text
        assert "Message B" in delivered_text
        assert "Message C" in delivered_text
