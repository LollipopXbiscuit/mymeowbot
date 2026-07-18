# AI chat plugin — powered by Groq
import logging
from pyrogram import filters, enums
from pyrogram.client import Client
from pyrogram.types import Message
from Adarsh.bot import StreamBot
from Adarsh.vars import Var

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Groq client setup
# ---------------------------------------------------------------------------
try:
    from groq import AsyncGroq
    _groq_client = AsyncGroq(api_key=Var.GROQ_API_KEY) if Var.GROQ_API_KEY else None
except Exception as e:
    logger.warning(f"Groq client could not be initialised: {e}")
    _groq_client = None

# Per-user conversation history  {user_id: [{"role": ..., "content": ...}]}
_history: dict = {}
_MAX_TURNS = 10   # keep last 10 user+assistant pairs in context

SYSTEM_PROMPT = (
    "You are Meow, an adorable and witty cat-girl AI assistant living inside a "
    "Telegram bot. You have a playful, warm personality and occasionally sprinkle "
    "in cute cat expressions (Nyaa~, meow, ~, 🐾, ✨) without overdoing it. "
    "You are genuinely helpful and give accurate, concise answers. "
    "Always respond in the same language the user writes in."
)


# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------
async def _ask(user_id: int, text: str) -> str:
    """Send a message to Groq and return the reply text."""
    if not _groq_client:
        return (
            "Nyaa~! My AI brain isn't wired up yet! 🐾\n"
            "The bot owner needs to set the `GROQ_API_KEY` secret."
        )

    history = _history.setdefault(user_id, [])
    history.append({"role": "user", "content": text})

    # Build message list: system prompt + trimmed history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history[-(  _MAX_TURNS * 2):]

    try:
        completion = await _groq_client.chat.completions.create(
            messages=messages,
            model=Var.GROQ_MODEL,
            max_tokens=1024,
        )
        reply = completion.choices[0].message.content or "…"
        history.append({"role": "assistant", "content": reply})
        # Trim stored history to avoid unbounded growth
        if len(history) > _MAX_TURNS * 2:
            _history[user_id] = history[-(_MAX_TURNS * 2):]
        return reply
    except Exception as e:
        logger.error(f"Groq error for user {user_id}: {e}")
        return f"Nyaa~! Something went wrong on my end 😿\n`{str(e)[:120]}`"


# ---------------------------------------------------------------------------
# /ai command — works everywhere (private + groups)
# ---------------------------------------------------------------------------
@StreamBot.on_message(filters.command("ai"), group=1)
async def ai_command_handler(c: Client, m: Message):
    if not m.command or len(m.command) < 2:
        await m.reply_text(
            "Nyaa~! Tell me what you want to know~ 🐾\n"
            "Usage: `/ai <your question>`",
            parse_mode=enums.ParseMode.MARKDOWN,
        )
        return

    query = " ".join(m.command[1:])
    thinking = await m.reply_text("Nyaa~! Thinking… 🐾✨")
    reply = await _ask(m.from_user.id, query)
    await thinking.edit_text(reply)


# ---------------------------------------------------------------------------
# /clearai — reset conversation history for the user
# ---------------------------------------------------------------------------
@StreamBot.on_message(filters.command("clearai"), group=1)
async def clear_ai_handler(c: Client, m: Message):
    _history.pop(m.from_user.id, None)
    await m.reply_text("Nyaa~! I've forgotten our conversation~ 🐾 Fresh start!")


# ---------------------------------------------------------------------------
# Private-chat fallback — any plain text that isn't a command goes to AI
# ---------------------------------------------------------------------------
@StreamBot.on_message(filters.private & filters.text, group=2)
async def ai_private_handler(c: Client, m: Message):
    # Skip if it's a command (handled by dedicated handlers in group 0/1)
    if m.text and m.text.startswith("/"):
        return

    thinking = await m.reply_text("Nyaa~! Thinking… 🐾✨")
    reply = await _ask(m.from_user.id, m.text)
    await thinking.edit_text(reply)
