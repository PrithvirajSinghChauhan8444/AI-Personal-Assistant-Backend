import asyncio
import html
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from telegram.constants import ParseMode
from telegram.error import BadRequest, RetryAfter, TelegramError

from modules.adapters.telegram.formatter import (
    markdown_to_telegram_html,
    split_markdown,
)

logger = logging.getLogger("TelegramMessageQueue")


def is_quota_or_rate_limit_error(err: Any) -> bool:
    """Detects whether an exception or message corresponds to an API quota or rate limit error."""
    err_str = str(err).lower()
    indicators = [
        "429",
        "resourceexhausted",
        "resource has been exhausted",
        "quota exceeded",
        "quota_exceeded",
        "rate limit",
        "ratelimit",
        "too many requests",
        "insufficient_quota",
        "tokens per minute",
        "requests per minute",
        "tpm",
        "rpm",
        "bandwidth limit",
    ]
    return any(ind in err_str for ind in indicators)


def format_failure_message(err: Any) -> str:
    """
    Creates a dedicated, user-friendly HTML failure message explaining
    what went wrong and providing actionable troubleshooting steps.
    """
    err_str = str(err).strip()
    is_quota = is_quota_or_rate_limit_error(err)

    if is_quota:
        return (
            "🚨 <b>API Quota / Rate Limit Exceeded</b>\n\n"
            "The assistant's LLM provider rejected the request because the API quota or rate limit has been exhausted.\n\n"
            f"<b>Details:</b> <code>{html.escape(err_str[:400])}</code>\n\n"
            "💡 <b>Actionable Solutions:</b>\n"
            "• <b>Wait a moment:</b> Free-tier API quotas often reset within 1–2 minutes.\n"
            "• <b>Switch LLM Provider:</b> In your <code>.env</code> file, you can switch providers without restart:\n"
            "   ↳ <code>MODEL_PROVIDER=groq</code> (generous free rate limits)\n"
            "   ↳ <code>MODEL_PROVIDER=ollama</code> (runs completely locally and offline)\n"
            "• <b>Update Key:</b> Provide a new Gemini/OpenAI API key in <code>.env</code>."
        )

    return (
        "⚠️ <b>Execution Failure Encountered</b>\n\n"
        "The assistant was unable to complete your instruction due to a system or worker failure.\n\n"
        f"<b>Error Details:</b>\n<code>{html.escape(err_str[:400])}</code>\n\n"
        "💡 <i>Tip: You can start a clean thread using <code>/new</code> or check worker status using <code>/workers</code>.</i>"
    )


class OutboundMessageQueue:
    """
    Asynchronous Outbound Telegram Message Queue.
    - Prevents flooding Telegram's API with rapid sequential outputs.
    - Batches consecutive messages for the same chat within a short window.
    - Rate-limits transmissions (~1 message per second per chat).
    - Automatically handles Telegram 429 RetryAfter backoffs.
    """

    def __init__(
        self,
        send_fn: Callable[[int, str, Optional[str]], Any],
        batch_window_seconds: float = 0.6,
        send_interval_seconds: float = 0.9,
    ):
        self._send_fn = send_fn
        self.batch_window_seconds = batch_window_seconds
        self.send_interval_seconds = send_interval_seconds

        self._queue: asyncio.Queue[Tuple[int, str]] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self) -> None:
        """Starts the background outbound queue worker."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("Outbound Telegram message queue worker started.")

    async def stop(self) -> None:
        """Stops the queue worker gracefully after flushing remaining items."""
        if self._running:
            self._running = False
            if self._worker_task:
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass
            logger.info("Outbound Telegram message queue worker stopped.")

    def enqueue(self, chat_id: int, text: str) -> None:
        """Enqueues a message for rate-limited, batched delivery."""
        if not text or not text.strip():
            return
        self._queue.put_nowait((chat_id, text.strip()))

    async def _worker_loop(self) -> None:
        """Continuous consumer loop with batching and backoff."""
        while self._running:
            try:
                chat_id, first_text = await self._queue.get()
                batched_texts = [first_text]

                # Collect any other pending messages for the same chat within batch window
                await asyncio.sleep(self.batch_window_seconds)
                extra_items: List[Tuple[int, str]] = []

                while not self._queue.empty():
                    try:
                        cid, txt = self._queue.get_nowait()
                        if cid == chat_id:
                            batched_texts.append(txt)
                        else:
                            extra_items.append((cid, txt))
                        self._queue.task_done()
                    except asyncio.QueueEmpty:
                        break

                # Re-queue items intended for other chats
                for item in extra_items:
                    self._queue.put_nowait(item)

                self._queue.task_done()

                # Combine batched texts cleanly
                combined_text = "\n\n".join(batched_texts)
                await self._deliver_message(chat_id, combined_text)

                # Rate-limit between messages
                await asyncio.sleep(self.send_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in outbound message queue loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _deliver_message(self, chat_id: int, text: str) -> None:
        """Splits and sends formatted message chunks with automatic RetryAfter backoff."""
        chunks = split_markdown(text)
        for chunk in chunks:
            html_chunk = markdown_to_telegram_html(chunk)
            sent = False
            attempts = 0

            while not sent and attempts < 3:
                attempts += 1
                try:
                    await self._send_fn(chat_id, html_chunk, ParseMode.HTML)
                    sent = True
                except RetryAfter as e:
                    wait_time = float(e.retry_after) + 0.5
                    logger.warning(f"Telegram 429 RetryAfter triggered. Backing off for {wait_time}s")
                    await asyncio.sleep(wait_time)
                except BadRequest as e:
                    logger.warning(f"HTML send failed ({e}); falling back to plain text")
                    try:
                        await self._send_fn(chat_id, chunk, None)
                        sent = True
                    except Exception as fallback_err:
                        logger.error(f"Plain text fallback send failed: {fallback_err}")
                        sent = True
                except Exception as e:
                    logger.error(f"Error delivering message to chat {chat_id}: {e}")
                    await asyncio.sleep(1.0)
