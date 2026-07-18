# Group allowlist — bot leaves any group not explicitly allowed by the owner.
import logging
from pyrogram import filters, Client
from pyrogram.types import Message, ChatMemberUpdated
from Adarsh.bot import StreamBot
from Adarsh.vars import Var
from Adarsh.utils.database import Database

logger = logging.getLogger(__name__)
db = Database(Var.DATABASE_URL, Var.name)

LEAVE_MSG = "i only serve for @waifuscollectorbot 😾"


# ── Helper ────────────────────────────────────────────────────────────────────

def _is_owner(user_id: int) -> bool:
    return user_id in Var.OWNER_ID


# ── Auto-leave when added to an un-allowed group ──────────────────────────────

@StreamBot.on_message(filters.new_chat_members, group=-1)
async def on_added_to_group(c: Client, m: Message):
    """Fires whenever the bot (or anyone) is added to a group."""
    if not m.new_chat_members:
        return
    bot_id = (c.me or await c.get_me()).id
    bot_was_added = any(u.id == bot_id for u in m.new_chat_members)
    if not bot_was_added:
        return

    chat_id = m.chat.id
    try:
        allowed = await db.is_group_allowed(chat_id)
    except Exception:
        # DB unreachable — default to leaving to be safe
        allowed = False

    if not allowed:
        try:
            await m.reply_text(LEAVE_MSG)
        except Exception:
            pass
        await c.leave_chat(chat_id)
        logger.info(f"[groups] Left un-allowed group {chat_id}")


# ── /allow — add a group to the allowlist ─────────────────────────────────────

@StreamBot.on_message(filters.command("allow") & filters.user(list(Var.OWNER_ID)))
async def allow_group(c: Client, m: Message):
    """
    Usage (send from the target group, or from anywhere with a group ID):
      /allow           — allow the current group
      /allow -100xyz   — allow the given group ID
    """
    args = m.command[1:]

    if args:
        try:
            target = int(args[0])
        except ValueError:
            await m.reply_text("❌ Invalid group ID. Usage: `/allow -100xxxxxxxxx`")
            return
    elif m.chat.type.name in ("GROUP", "SUPERGROUP"):
        target = m.chat.id
    else:
        await m.reply_text(
            "Send `/allow` inside the group you want to allow, "
            "or pass the group ID: `/allow -100xxxxxxxxx`"
        )
        return

    try:
        await db.add_allowed_group(target)
        await m.reply_text(f"✅ Group `{target}` is now allowed.")
    except Exception as e:
        await m.reply_text(f"❌ DB error: {e}")


# ── /disallow — remove a group from the allowlist ────────────────────────────

@StreamBot.on_message(filters.command("disallow") & filters.user(list(Var.OWNER_ID)))
async def disallow_group(c: Client, m: Message):
    """
    Usage:
      /disallow           — disallow the current group
      /disallow -100xyz   — disallow the given group ID
    """
    args = m.command[1:]

    if args:
        try:
            target = int(args[0])
        except ValueError:
            await m.reply_text("❌ Invalid group ID. Usage: `/disallow -100xxxxxxxxx`")
            return
    elif m.chat.type.name in ("GROUP", "SUPERGROUP"):
        target = m.chat.id
    else:
        await m.reply_text(
            "Send `/disallow` inside the group you want to remove, "
            "or pass the group ID: `/disallow -100xxxxxxxxx`"
        )
        return

    try:
        await db.remove_allowed_group(target)
        await m.reply_text(f"✅ Group `{target}` removed from allowlist. Bot will leave if re-added.")
    except Exception as e:
        await m.reply_text(f"❌ DB error: {e}")


# ── /allowedgroups — list all allowed groups ─────────────────────────────────

@StreamBot.on_message(filters.command("allowedgroups") & filters.user(list(Var.OWNER_ID)))
async def list_allowed(c: Client, m: Message):
    try:
        groups = await db.get_allowed_groups()
    except Exception as e:
        await m.reply_text(f"❌ DB error: {e}")
        return

    if not groups:
        await m.reply_text("No groups are allowed yet. Use `/allow` inside a group or pass its ID.")
        return

    lines = "\n".join(f"• `{gid}`" for gid in groups)
    await m.reply_text(f"**Allowed groups ({len(groups)}):**\n{lines}")
