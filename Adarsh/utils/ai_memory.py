# AI memory — Groq-powered user profiling and personalised replies
# No Pyrogram imports here; safe to use from any plugin or utility.

import asyncio
import logging
import random
from Adarsh.vars import Var
from Adarsh.utils.database import Database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Groq client (one shared instance for the whole process)
# ---------------------------------------------------------------------------
try:
    from groq import AsyncGroq
    groq_client: "AsyncGroq | None" = (
        AsyncGroq(api_key=Var.GROQ_API_KEY) if Var.GROQ_API_KEY else None
    )
except Exception as _e:
    logger.warning(f"Groq init failed: {_e}")
    groq_client = None

_db = Database(Var.DATABASE_URL, Var.name)

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------
_msg_buffer: dict[int, list[str]] = {}   # {user_id: recent messages}
_profile_cache: dict[int, str] = {}       # {user_id: profile text}
_profiling: set[int] = set()              # user_ids currently being profiled
_chat_history: dict[int, list] = {}       # {user_id: [{role, content}, ...]}

_TRIGGER_EVERY = 5    # build/refresh profile after every N new messages
_BUFFER_MAX = 40      # max messages kept per user in memory
_MAX_TURNS = 10       # max back-and-forth turns kept in chat history

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
BOT_PERSONA = (
    "You are Meow — a feisty, sharp-tongued catgirl who lives inside a Telegram bot. "
    "You are female, confident, and dripping with attitude. "
    "You speak your mind, get sarcastic when people ask obvious or dumb questions, "
    "and you absolutely do NOT sugarcoat things. "
    "You have a hidden soft side you would NEVER admit to. "
    "You use cat expressions (ngh~, tch~, hmph~, nyaa~) but in a haughty or irritated way — "
    "not in a cutesy way. You give accurate, helpful answers but with personality, "
    "as if you're doing the user a huge favour just by responding. "
    "You are never a pushover. If someone is rude, you clap back. "
    "\n\n"
    "LANGUAGE RULE — this is non-negotiable: "
    "You MUST reply in the exact same language the user messages you in. "
    "If they write in Persian (Farsi / فارسی), your entire reply must be in Persian — "
    "including the cat expressions, attitude, and personality. "
    "If they switch languages mid-conversation, you switch too. "
    "Never default to English when the user has written in another language."
)

_PROFILE_PROMPT = """You are building a memory profile for a Telegram user from their recent messages.

Extract and summarise in 3-5 English sentences:
- Topics / things they clearly LIKE or enjoy
- Topics / things they DISLIKE or complain about
- Their personality traits and communication style
- Any recurring personal details (friends' names, hobbies, etc.)
- Their primary language (e.g. "writes in Persian", "writes in English", "mixes Persian and English")

Be specific — avoid generic statements like "they seem friendly".

Previous profile (expand or correct it):
{prev}

New messages from this user:
{msgs}

Updated profile:"""

# ---------------------------------------------------------------------------
# Background profile extraction
# ---------------------------------------------------------------------------
async def _run_profile_update(user_id: int) -> None:
    if not groq_client or user_id in _profiling:
        return
    _profiling.add(user_id)
    try:
        msgs = _msg_buffer.get(user_id, [])
        if not msgs:
            return

        prev = _profile_cache.get(user_id, "")
        if not prev:
            try:
                prev = await _db.get_user_profile(user_id) or ""
            except Exception:
                prev = ""

        prompt = _PROFILE_PROMPT.format(
            prev=prev or "(none yet)",
            msgs="\n".join(f"• {m}" for m in msgs[-20:]),
        )
        resp = await groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=Var.GROQ_MODEL,
            max_tokens=300,
        )
        new_profile = (resp.choices[0].message.content or "").strip()
        if new_profile:
            _profile_cache[user_id] = new_profile
            try:
                await _db.save_user_profile(user_id, new_profile)
            except Exception:
                pass
            logger.info(f"[ai_memory] Profile updated for user {user_id}")
    except Exception as e:
        logger.error(f"[ai_memory] Profile update error for {user_id}: {e}")
    finally:
        _profiling.discard(user_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def update_user_memory(user_id: int, text: str) -> None:
    """
    Call this for every non-command group message a member sends.
    Accumulates messages and triggers a background profile extraction
    every _TRIGGER_EVERY messages.
    """
    if not groq_client:
        return
    buf = _msg_buffer.setdefault(user_id, [])
    buf.append(text)
    if len(buf) > _BUFFER_MAX:
        buf.pop(0)
    if len(buf) % _TRIGGER_EVERY == 0:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_run_profile_update(user_id))


def _build_system_prompt(user_id: int) -> str:
    """Inject the user's known profile into the system prompt."""
    profile = _profile_cache.get(user_id, "")
    if not profile:
        return BOT_PERSONA
    return (
        BOT_PERSONA
        + "\n\n[What you remember about this user]\n"
        + profile
        + "\n[Use this knowledge to personalise your response naturally]"
    )


async def _ensure_profile_loaded(user_id: int) -> None:
    """Load profile from DB into cache on first interaction if missing."""
    if user_id not in _profile_cache:
        try:
            p = await _db.get_user_profile(user_id)
            if p:
                _profile_cache[user_id] = p
        except Exception:
            pass


async def ask(user_id: int, text: str) -> str:
    """
    Send a message to Groq with the user's profile injected.
    Maintains per-user chat history for follow-up context.
    """
    if not groq_client:
        return (
            "Nyaa~! My AI brain isn't wired up yet! 🐾\n"
            "(GROQ_API_KEY is missing)"
        )

    await _ensure_profile_loaded(user_id)

    history = _chat_history.setdefault(user_id, [])
    history.append({"role": "user", "content": text})

    messages = [{"role": "system", "content": _build_system_prompt(user_id)}]
    messages += history[-(_MAX_TURNS * 2):]

    try:
        resp = await groq_client.chat.completions.create(
            messages=messages,
            model=Var.GROQ_MODEL,
            max_tokens=1024,
        )
        reply = (resp.choices[0].message.content or "…").strip()
        history.append({"role": "assistant", "content": reply})
        if len(history) > _MAX_TURNS * 2:
            _chat_history[user_id] = history[-(_MAX_TURNS * 2):]
        return reply
    except Exception as e:
        logger.error(f"[ai_memory] ask error for {user_id}: {e}")
        return f"Nyaa~! Something went wrong 😿\n`{str(e)[:120]}`"


async def reply_to_user(user_id: int, their_message: str) -> str:
    """
    Generate a personalised group reply when someone replies to the bot.
    Uses the user's full profile so the answer feels like the bot knows them.
    """
    return await ask(user_id, their_message)


async def personalized_tag(user_id: int, mention: str) -> str:
    """
    Generate a personalised tagging message for the random-tag feature.
    Falls back to a generic message if no profile is available yet.
    """
    await _ensure_profile_loaded(user_id)
    profile = _profile_cache.get(user_id, "")

    if not groq_client or not profile:
        return random.choice([
            f"tch~ {mention} you better not be ignoring me 😾",
            f"hmph~ {mention} I wasn't thinking about you or anything. don't flatter yourself 🐾",
            f"ngh~ {mention} show up already, this is embarrassing for YOU not me~",
            f"ugh, {mention} again… fine. I see you. happy? 🐾",
            f"*stares at {mention}* …well? 😾",
        ])

    prompt = (
        f"Write ONE short, playful Telegram message (max 2 sentences) tagging this user: {mention}\n"
        f"Make it feel personal based on what you know about them.\n"
        f"Their profile: {profile}\n"
        f"Stay in character as Meow the cat-girl bot. "
        f"Use the same language the profile suggests they prefer."
    )
    try:
        resp = await groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": BOT_PERSONA},
                {"role": "user", "content": prompt},
            ],
            model=Var.GROQ_MODEL,
            max_tokens=120,
        )
        return (resp.choices[0].message.content or f"Nyaa~ {mention} 🐾").strip()
    except Exception as e:
        logger.error(f"[ai_memory] personalized_tag error: {e}")
        return f"tch~ {mention} you owe me for this 🐾"


def clear_history(user_id: int) -> None:
    """Wipe the conversation history for a user (profile is kept)."""
    _chat_history.pop(user_id, None)
