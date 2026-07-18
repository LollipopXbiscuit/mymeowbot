# AI chat plugin — command handlers only.
# All memory/profile logic lives in Adarsh/utils/ai_memory.py
import logging
from pyrogram import filters, enums
from pyrogram.client import Client
from pyrogram.types import Message
from Adarsh.bot import StreamBot
from Adarsh.utils.ai_memory import ask, clear_history

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# /ai <question> — works in groups and private chat
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
    reply = await ask(m.from_user.id, query)
    await thinking.edit_text(reply)


# ---------------------------------------------------------------------------
# /clearai — wipe conversation history (profile is kept)
# ---------------------------------------------------------------------------
@StreamBot.on_message(filters.command("clearai"), group=1)
async def clear_ai_handler(c: Client, m: Message):
    clear_history(m.from_user.id)
    await m.reply_text("Nyaa~! I've forgotten our chat history~ 🐾 Fresh start!\n(Your profile is still saved.)")


# ---------------------------------------------------------------------------
# Private chat fallback — any plain text goes to AI
# ---------------------------------------------------------------------------
@StreamBot.on_message(filters.private & filters.text, group=2)
async def ai_private_handler(c: Client, m: Message):
    if m.text and m.text.startswith("/"):
        return
    thinking = await m.reply_text("Nyaa~! Thinking… 🐾✨")
    reply = await ask(m.from_user.id, m.text)
    await thinking.edit_text(reply)
