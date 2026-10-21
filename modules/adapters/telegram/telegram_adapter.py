import asyncio
import html
import logging
import os
import re
import threading
import uuid
from typing import Dict, List, Optional, Set

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from modules.adapters.base_adapter import BaseAdapter
from modules.adapters.telegram.formatter import (
    markdown_to_telegram_html,
    split_markdown,
)
from modules.adapters.telegram.message_queue import (
    OutboundMessageQueue,
    format_failure_message,
    is_quota_or_rate_limit_error,
)
from modules.integration.application_orchestrator import ApplicationOrchestrator

logger = logging.getLogger("TelegramAdapter")

split_message = split_markdown


class TelegramAdapter(BaseAdapter):
    """
    Pluggable Telegram Client Adapter.
    Enables secure, asynchronous, remote interaction with the AI Personal Assistant.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        allowed_user_ids: Optional[List[int]] = None,
        orchestrator: Optional[ApplicationOrchestrator] = None,
        coordinator: Optional[Any] = None,
    ):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self._running = False
        self._app: Optional[Application] = None
        self._msg_queue: Optional[OutboundMessageQueue] = None

        # Load and parse allowed user IDs
        if allowed_user_ids is not None:
            self.allowed_user_ids: Set[int] = set(allowed_user_ids)
        else:
            raw_ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
            self.allowed_user_ids = {
                int(uid.strip())
                for uid in raw_ids.split(",")
                if uid.strip().isdigit()
            }

        # Session tracking: chat_id -> current session/thread ID
        self._sessions: Dict[int, str] = {}

        # Core cognitive orchestrator and optional remote control coordinator
        self._orchestrator = orchestrator
        self._coordinator = coordinator

    @property
    def coordinator(self) -> Optional[Any]:
        return self._coordinator

    @property
    def orchestrator(self) -> ApplicationOrchestrator:
        if self._orchestrator is None:
            self._orchestrator = ApplicationOrchestrator()
        return self._orchestrator

    def is_authorized(self, user_id: int) -> bool:
        """Checks if the user ID is in the authorized whitelist."""
        if not self.allowed_user_ids:
            return False
        return user_id in self.allowed_user_ids

    def get_session_id(self, chat_id: int) -> str:
        """Gets or initializes the active thread ID for a chat."""
        if self._coordinator:
            return self._coordinator.session_id
        if chat_id not in self._sessions:
            self._sessions[chat_id] = f"tg_{chat_id}_{uuid.uuid4().hex[:6]}"
        return self._sessions[chat_id]

    def reset_session(self, chat_id: int) -> str:
        """Generates a fresh thread ID to clear conversation context."""
        if self._coordinator:
            new_session = f"remote_{uuid.uuid4().hex[:8]}"
            self._coordinator.session_id = new_session
            self._coordinator.chat_history.clear()
            self._coordinator.working_memory.clear()
            self._coordinator.completed_tasks.clear()
            self._coordinator.turns.clear()
            return new_session

        new_session = f"tg_{chat_id}_{uuid.uuid4().hex[:6]}"
        self._sessions[chat_id] = new_session
        return new_session

    async def _send_typing_heartbeat(self, chat_id: int, stop_event: asyncio.Event) -> None:
        """Sends periodic TYPING chat actions while the assistant is processing."""
        while not stop_event.is_set():
            try:
                if self._app and self._app.bot:
                    await self._app.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                pass

    async def _progress_updater(
        self,
        status_msg,
        queue: asyncio.Queue,
        stop_event: asyncio.Event,
    ) -> None:
        """Pulls progress events from queue and edits status_msg with rate limiting."""
        history: List[str] = ["🧠 Understanding query & planning execution..."]
        last_edit_time = 0.0

        while not stop_event.is_set() or not queue.empty():
            try:
                try:
                    update_text = await asyncio.wait_for(queue.get(), timeout=0.6)
                    if update_text and update_text not in history:
                        history.append(update_text)
                        if len(history) > 5:
                            history = history[-5:]
                    queue.task_done()
                except asyncio.TimeoutError:
                    pass

                now = asyncio.get_event_loop().time()
                # Rate-limit edits to at most once every 1.1s to respect Telegram limits
                if now - last_edit_time >= 1.1:
                    bullet_points = "\n".join(f"• {html.escape(line)}" for line in history)
                    content = f"⏳ <b>Working on your request...</b>\n\n{bullet_points}"
                    try:
                        await status_msg.edit_text(content, parse_mode=ParseMode.HTML)
                        last_edit_time = now
                    except Exception:
                        pass
            except Exception:
                pass

    async def _send_safe_message(self, update: Update, text: str) -> None:
        """Sends message chunks safely with Telegram HTML formatting and rate-limited queueing."""
        if not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        if self._msg_queue:
            self._msg_queue.enqueue(chat_id, text)
            return

        chunks = split_markdown(text)
        for chunk in chunks:
            html_chunk = markdown_to_telegram_html(chunk)
            try:
                await update.effective_chat.send_message(html_chunk, parse_mode=ParseMode.HTML)
            except Exception as html_err:
                logger.warning(f"Failed to send HTML message ({html_err}); falling back to plain text")
                try:
                    await update.effective_chat.send_message(chunk, parse_mode=None)
                except Exception as plain_err:
                    logger.error(f"Failed to send plain text message: {plain_err}")

    # -------------------------------------------------------------------------
    # Command Handlers
    # -------------------------------------------------------------------------

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /start command."""
        user = update.effective_user
        if not user or not update.effective_message:
            return

        user_id = user.id
        authorized = self.is_authorized(user_id)

        if not authorized:
            await update.effective_message.reply_text(
                f"⛔ <b>Access Denied</b>\n\n"
                f"Your Telegram User ID is: <code>{user_id}</code>\n\n"
                f"This AI Assistant has access to private personal tools and accounts.\n"
                f"To authorize this account, please add your ID to <code>TELEGRAM_ALLOWED_USER_IDS</code> in your .env file.\n\n"
                f"Example:\n<code>TELEGRAM_ALLOWED_USER_IDS={user_id}</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        session_id = self.get_session_id(update.effective_chat.id)
        welcome_msg = (
            f"👋 <b>Welcome, {html.escape(user.first_name)}! Authorized Connection Established.</b>\n\n"
            f"🤖 <b>AI Personal Assistant</b> is online and ready.\n"
            f"• <b>Session ID:</b> <code>{session_id}</code>\n"
            f"• <b>Workers:</b> 12 modular workers ready\n\n"
            f"Send any message or instruction to begin, or use <code>/help</code> for commands."
        )
        await update.effective_message.reply_text(welcome_msg, parse_mode=ParseMode.HTML)

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /help command."""
        if not update.effective_user or not self.is_authorized(update.effective_user.id):
            return

        help_text = (
            "📖 <b>Available Commands:</b>\n\n"
            "• <code>/remote</code> - View Remote Control status & active connection\n"
            "• <code>/remote_control</code> - Alias for /remote\n"
            "• <code>/new</code> - Reset session context & start a fresh thread\n"
            "• <code>/session</code> - View current session thread ID\n"
            "• <code>/export</code> - Download clean conversation transcript (.md)\n"
            "• <code>/export_verbose</code> - Download detailed execution transcript (.md)\n"
            "• <code>/workers</code> - List registered modular workers & categories\n"
            "• <code>/status</code> - Check assistant system & remote control status\n"
            "• <code>/help</code> - Show this command reference\n\n"
            "💡 <b>Tip:</b> You can ask the assistant to check your emails, manage calendar events, "
            "search the web, run system commands, search YouTube, and more."
        )
        if update.effective_chat:
            await update.effective_chat.send_message(help_text, parse_mode=ParseMode.HTML)

    async def handle_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /new command to reset conversational thread."""
        if not update.effective_user or not self.is_authorized(update.effective_user.id):
            return

        chat_id = update.effective_chat.id
        new_session = self.reset_session(chat_id)
        await update.effective_message.reply_text(
            f"🔄 <b>Started new conversation session!</b>\n<code>Thread ID: {new_session}</code>",
            parse_mode=ParseMode.HTML,
        )

    async def handle_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /session command to view thread ID."""
        if not update.effective_user or not self.is_authorized(update.effective_user.id):
            return

        chat_id = update.effective_chat.id
        session_id = self.get_session_id(chat_id)
        await update.effective_message.reply_text(
            f"🧵 <b>Current Session Thread ID:</b>\n<code>{session_id}</code>",
            parse_mode=ParseMode.HTML,
        )

    async def handle_workers(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /workers command."""
        if not update.effective_user or not self.is_authorized(update.effective_user.id):
            return

        workers = self.orchestrator.workers
        lines = [f"📦 <b>Registered Modular Workers ({len(workers)}):</b>\n"]
        for w in workers:
            cats = ", ".join(w.categories)
            lines.append(f"• <b>{html.escape(w.name)}</b> — <code>{html.escape(cats)}</code>")

        if update.effective_chat:
            await update.effective_chat.send_message("\n".join(lines), parse_mode=ParseMode.HTML)

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /status command."""
        if not update.effective_user or not self.is_authorized(update.effective_user.id):
            return

        chat_id = update.effective_chat.id
        session_id = self.get_session_id(chat_id)
        mode_str = "🌐 Remote Control (CLI + Telegram)" if self._coordinator else "📱 Standalone Telegram Gateway"
        active_src = (self._coordinator.active_source or "None").upper() if self._coordinator else "TELEGRAM"
        turns_count = len(self._coordinator.turns) if self._coordinator else len(self._sessions)

        status_msg = (
            f"🟢 <b>System Status: Operational</b>\n\n"
            f"• <b>Mode:</b> {mode_str}\n"
            f"• <b>Active Source:</b> <code>{active_src}</code>\n"
            f"• <b>Active Session:</b> <code>{session_id}</code>\n"
            f"• <b>Total Turns:</b> <code>{turns_count}</code>\n"
            f"• <b>Workers Registered:</b> <code>{len(self.orchestrator.workers)}</code>\n"
            f"• <b>Storage:</b> Unified Storage Initialized\n"
            f"• <b>Security:</b> User Whitelist Active\n"
        )
        if update.effective_chat:
            await update.effective_chat.send_message(status_msg, parse_mode=ParseMode.HTML)

    async def handle_export(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /export command to export conversation file on demand."""
        if not update.effective_user or not self.is_authorized(update.effective_user.id):
            return

        args = context.args or []
        verbose = any(a.lower() in ("verbose", "-v", "--verbose") for a in args)
        await self._send_export_document(update, verbose=verbose)

    async def handle_export_verbose(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles /export_verbose command to export full verbose execution transcript."""
        if not update.effective_user or not self.is_authorized(update.effective_user.id):
            return

        await self._send_export_document(update, verbose=True)

    async def handle_export_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles inline keyboard button callbacks for conversation export."""
        query = update.callback_query
        if not query or not update.effective_user or not self.is_authorized(update.effective_user.id):
            return

        await query.answer()
        verbose = query.data == "export_verbose"
        await self._send_export_document(update, verbose=verbose)

    async def _send_export_document(self, update: Update, verbose: bool = False) -> None:
        """Generates and uploads conversation document file to Telegram (Rule 2)."""
        chat_id = update.effective_chat.id if update.effective_chat else 0
        target_message = update.effective_message

        if not target_message and update.callback_query:
            target_message = update.callback_query.message

        if not target_message:
            return

        session_id = self.get_session_id(chat_id)
        file_path = None
        turn_count = 0

        if self._coordinator:
            if not self._coordinator.turns and not self._coordinator.chat_history:
                await target_message.reply_text(
                    "⚠️ <b>No conversation exchanges recorded yet in this session.</b>",
                    parse_mode=ParseMode.HTML,
                )
                return
            file_path = self._coordinator.export_conversation_to_file(verbose=verbose)
            turn_count = len(self._coordinator.turns)
        else:
            from modules.adapters.remote_control.exporter import ConversationExporter
            from modules.infrastructure.storage.session_manager import load_session_context

            saved = load_session_context() or {}
            history = saved.get("chat_history", [])
            if not history:
                await target_message.reply_text(
                    "⚠️ <b>No conversation exchanges recorded yet.</b>",
                    parse_mode=ParseMode.HTML,
                )
                return
            content = ConversationExporter.format_clean(session_id, turns=[], chat_history=history)
            file_path = ConversationExporter.save_to_file(content, session_id, verbose=verbose)
            turn_count = len(history) // 2

        export_label = "Detailed Verbose" if verbose else "Clean Standard"
        caption = (
            f"📄 <b>Conversation Export ({export_label})</b>\n\n"
            f"• <b>Session:</b> <code>{session_id}</code>\n"
            f"• <b>Turns:</b> <code>{turn_count}</code>\n"
            f"• <b>Type:</b> <code>{'Verbose Execution Trace' if verbose else 'Clean Conversation'}</code>"
        )

        buttons = []
        if not verbose:
            buttons.append([InlineKeyboardButton("🔍 Get Verbose Export", callback_data="export_verbose")])
        else:
            buttons.append([InlineKeyboardButton("📄 Get Clean Export", callback_data="export_clean")])
        keyboard = InlineKeyboardMarkup(buttons)

        try:
            with open(file_path, "rb") as doc:
                await target_message.reply_document(
                    document=doc,
                    filename=os.path.basename(file_path),
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
        except Exception as e:
            logger.error(f"Failed to send export document: {e}")
            await target_message.reply_text(f"❌ Failed to deliver export file: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Processes incoming user text queries through the ApplicationOrchestrator."""
        user = update.effective_user
        if not user or not update.effective_message:
            return

        user_id = user.id
        if not self.is_authorized(user_id):
            await update.effective_message.reply_text(
                f"⛔ <b>Access Denied</b>. Your Telegram User ID is <code>{user_id}</code>.\n"
                "Please add this ID to <code>TELEGRAM_ALLOWED_USER_IDS</code> in your .env.",
                parse_mode=ParseMode.HTML,
            )
            return

        user_prompt = update.effective_message.text
        if not user_prompt or not user_prompt.strip():
            return

        chat_id = update.effective_chat.id
        session_id = self.get_session_id(chat_id)

        # 1. Send immediate visual status message
        status_msg = None
        try:
            status_msg = await update.effective_message.reply_text(
                "⏳ <b>Working on your request...</b>\n\n• 🧠 Understanding query & planning execution...",
                parse_mode=ParseMode.HTML,
            )
        except Exception as err:
            logger.warning(f"Could not send initial progress message: {err}")

        # 2. Setup progress bridge from synchronous worker thread to async event loop
        progress_queue: asyncio.Queue[str] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_progress_callback(msg: str) -> None:
            loop.call_soon_threadsafe(progress_queue.put_nowait, msg)

        stop_progress = asyncio.Event()
        updater_task = None
        if status_msg:
            updater_task = asyncio.create_task(
                self._progress_updater(status_msg, progress_queue, stop_progress)
            )

        # 3. Start continuous typing indicator
        stop_typing = asyncio.Event()
        typing_task = asyncio.create_task(self._send_typing_heartbeat(chat_id, stop_typing))

        response = ""
        is_error = False
        try:
            # Run execution via RemoteControlCoordinator (if in remote mode) or directly via ApplicationOrchestrator
            if self._coordinator:
                response = await asyncio.to_thread(
                    self._coordinator.execute_query,
                    user_prompt,
                    source="telegram",
                    on_progress=on_progress_callback,
                )
            else:
                response = await asyncio.to_thread(
                    self.orchestrator.run,
                    user_prompt,
                    thread_id=session_id,
                    on_progress=on_progress_callback,
                )
        except Exception as e:
            logger.exception("Error executing user prompt through orchestrator")
            response = f"❌ *Error during execution:*\n`{str(e)}`"
            is_error = True
        finally:
            stop_progress.set()
            stop_typing.set()
            if updater_task:
                await updater_task
            await typing_task

        # 4. Check for failure or quota exhaustion
        is_failure = (
            is_error
            or is_quota_or_rate_limit_error(response)
            or response.startswith("An execution error occurred:")
            or response.startswith("API Quota / Rate Limit Exceeded:")
        )

        if is_failure:
            failure_html = format_failure_message(response)
            if status_msg:
                try:
                    await status_msg.edit_text(failure_html, parse_mode=ParseMode.HTML)
                    return
                except Exception:
                    try:
                        await status_msg.edit_text(response, parse_mode=None)
                        return
                    except Exception:
                        pass
            await self._send_safe_message(update, failure_html)
            return

        # Normal successful completion: remove transient status message
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

        if not response or not response.strip():
            response = "*(No response generated by assistant)*"

        await self._send_safe_message(update, response)

    async def send_startup_greeting(self, bot) -> None:
        """Sends a startup greeting message to all authorized users when the server boots up."""
        if not self.allowed_user_ids:
            logger.info("No authorized users configured; skipping startup greeting.")
            return

        provider = os.getenv("MODEL_PROVIDER", "google").capitalize()
        model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        num_workers = len(self.orchestrator.workers)

        greeting_html = (
            "🚀 <b>AI Personal Assistant is Online!</b>\n\n"
            "The backend server has booted up successfully and remote control is active.\n\n"
            f"• <b>Status:</b> Operational\n"
            f"• <b>Active Workers:</b> <code>{num_workers} modular workers</code>\n"
            f"• <b>Model:</b> <code>{html.escape(provider)} ({html.escape(model)})</code>\n"
            f"• <b>Security:</b> Whitelist filter active\n\n"
            "Send any request or use <code>/help</code> to begin."
        )

        for user_id in self.allowed_user_ids:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=greeting_html,
                    parse_mode=ParseMode.HTML,
                )
                logger.info(f"Startup greeting delivered to user {user_id}")
            except Exception as e:
                logger.warning(
                    f"Could not deliver startup greeting to user {user_id} ({e}). "
                    "(Note: Users must send at least one message or /start to the bot before the bot can initiate messages)."
                )

    # -------------------------------------------------------------------------
    # Lifecycle Controls
    # -------------------------------------------------------------------------

    def build_application(self) -> Application:
        """Builds and configures the python-telegram-bot Application."""
        if not self.token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is not configured. "
                "Please set it in your .env or pass it to TelegramAdapter."
            )

        async def _post_init_hook(application: Application) -> None:
            if self._msg_queue:
                self._msg_queue.start()
            await self.send_startup_greeting(application.bot)

        async def _post_shutdown_hook(application: Application) -> None:
            if self._msg_queue:
                await self._msg_queue.stop()

        app = (
            ApplicationBuilder()
            .token(self.token)
            .post_init(_post_init_hook)
            .post_shutdown(_post_shutdown_hook)
            .build()
        )

        async def _bot_send_fn(chat_id: int, text: str, parse_mode: Optional[str]) -> None:
            if self._app and self._app.bot:
                await self._app.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)

        self._msg_queue = OutboundMessageQueue(send_fn=_bot_send_fn)

        # Register command handlers
        app.add_handler(CommandHandler("start", self.handle_start))
        app.add_handler(CommandHandler("help", self.handle_help))
        app.add_handler(CommandHandler("new", self.handle_new))
        app.add_handler(CommandHandler("reset", self.handle_new))
        app.add_handler(CommandHandler("session", self.handle_session))
        app.add_handler(CommandHandler("workers", self.handle_workers))
        app.add_handler(CommandHandler("status", self.handle_status))
        app.add_handler(CommandHandler("remote", self.handle_status))
        app.add_handler(CommandHandler("remote_control", self.handle_status))
        app.add_handler(CommandHandler("export", self.handle_export))
        app.add_handler(CommandHandler("export_verbose", self.handle_export_verbose))
        app.add_handler(CallbackQueryHandler(self.handle_export_callback, pattern="^export_"))

        # Register text message handler
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        self._app = app
        return app

    def start_background(self) -> threading.Thread:
        """Starts the Telegram bot polling in a dedicated background daemon thread."""
        def _run_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._app = self.build_application()
            self._running = True
            logger.info("Starting background Telegram bot polling...")
            try:
                self._app.run_polling(stop_signals=None, close_loop=True)
            except Exception as e:
                logger.error(f"Telegram polling thread error: {e}")
            finally:
                self._running = False
                logger.info("Background Telegram polling thread stopped.")

        thread = threading.Thread(target=_run_thread, daemon=True, name="TelegramPollingWorker")
        thread.start()
        return thread

    def start(self) -> None:
        """Starts the Telegram bot polling in blocking mode."""
        app = self.build_application()
        self._running = True
        logger.info("Starting Telegram bot polling...")
        app.run_polling()
        self._running = False

    def stop(self) -> None:
        """Gracefully stops the Telegram bot."""
        if self._running:
            self._running = False
            if self._msg_queue:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self._msg_queue.stop())
                except Exception:
                    pass
            if self._app:
                self._app.stop_running()
            logger.info("Telegram bot stopped.")

    def is_running(self) -> bool:
        return self._running
