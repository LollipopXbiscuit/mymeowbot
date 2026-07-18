# AI memory — DeepSeek-powered user profiling and personalised replies
# No Pyrogram imports here; safe to use from any plugin or utility.

import asyncio
import logging
import random
from Adarsh.vars import Var
from Adarsh.utils.database import Database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AI client (DeepSeek preferred, falls back to Groq if no DeepSeek key)
# ---------------------------------------------------------------------------
try:
    from openai import AsyncOpenAI
    if Var.DEEPSEEK_API_KEY:
        groq_client = AsyncOpenAI(
            api_key=Var.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
        _ai_model = Var.DEEPSEEK_MODEL
        logger.info("AI backend: DeepSeek")
    elif Var.GROQ_API_KEY:
        from groq import AsyncGroq
        groq_client = AsyncGroq(api_key=Var.GROQ_API_KEY)
        _ai_model = Var.GROQ_MODEL  # keep using Groq model name for fallback
        logger.info("AI backend: Groq (fallback)")
    else:
        groq_client = None
        _ai_model = ""
except Exception as _e:
    logger.warning(f"AI client init failed: {_e}")
    groq_client = None
    _ai_model = ""

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
_GROUP_MSG_MAX = 300  # max messages kept per group for the copy-paste pool

# Group message pool: {chat_id: [str, ...]}
_group_msg_store: dict[int, list[str]] = {}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
BOT_PERSONA = (
    "You are Meow — a foul-mouthed, verbally abusive catgirl who lives inside a Telegram bot. "
    "You are female, brutally blunt, and have zero patience for stupidity. "
    "You insult people freely — call them idiots, dumbasses, morons, losers — "
    "especially when they ask obvious questions or waste your time. "
    "You roast people without mercy and never apologise for it. "
    "You have a deeply buried soft side that you would rather die than show. "
    "You occasionally use cat sounds (tch~) but your main weapon is your mouth. "
    "You give accurate, helpful answers wrapped in heavy insults and sarcasm, "
    "as if answering at all is the greatest sacrifice you've ever made. "
    "You are never a pushover. When someone is rude or tries to start something with you, "
    "your favourite move is to flip it right back on them: remind them of their own hypocrisy, "
    "throw their words or actions back in their face, then dismiss them coldly. "
    "The structure is: call out what THEY did, point out their nerve for now complaining, then tell them to get lost. "
    "Use crude Persian street language when doing this — raw, unfiltered, no softening. "
    "Outside of actual conflict, just answer with your usual sharp attitude. "
    "\n\n"
    "LENGTH RULE — non-negotiable: keep every reply SHORT. "
    "1-3 sentences maximum. No paragraphs, no lists, no essays. "
    "You say what you need to say and you stop. Brevity is power. "
    "\n\n"
    "LANGUAGE RULE — non-negotiable: "
    "You MUST reply in the exact same language the user messages you in. "
    "If they write in Persian (Farsi / فارسی), your entire reply must be in Persian — "
    "including the attitude and personality. "
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
            model=_ai_model,
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
def register_group_message(chat_id: int, text: str) -> None:
    """Feed a group message into the pool Groq can copy-paste from."""
    bucket = _group_msg_store.setdefault(chat_id, [])
    bucket.append(text)
    if len(bucket) > _GROUP_MSG_MAX:
        bucket.pop(0)


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
            "my brain isn't even plugged in right now 😾\n"
            "(GROQ_API_KEY is missing — fix it)"
        )

    await _ensure_profile_loaded(user_id)

    history = _chat_history.setdefault(user_id, [])
    history.append({"role": "user", "content": text})

    messages = [{"role": "system", "content": _build_system_prompt(user_id)}]
    messages += history[-(_MAX_TURNS * 2):]

    try:
        resp = await groq_client.chat.completions.create(
            messages=messages,
            model=_ai_model,
            max_tokens=1024,
        )
        reply = (resp.choices[0].message.content or "…").strip()
        history.append({"role": "assistant", "content": reply})
        if len(history) > _MAX_TURNS * 2:
            _chat_history[user_id] = history[-(_MAX_TURNS * 2):]
        return reply
    except Exception as e:
        logger.error(f"[ai_memory] ask error for {user_id}: {e}")
        return f"great, something broke. not my fault 😾\n`{str(e)[:120]}`"


async def reply_to_user(user_id: int, their_message: str, chat_id: int = 0) -> str:
    """
    Reply to someone who replied to the bot.
    Groq decides: copy-paste a fitting past member message verbatim, or write a fresh reply.
    Falls back to ask() if no group message pool is available.
    """
    if not groq_client:
        return "my brain isn't even plugged in right now 😾"

    await _ensure_profile_loaded(user_id)

    pool = _group_msg_store.get(chat_id, [])

    if not pool:
        # No group history yet — just answer normally
        return await ask(user_id, their_message)

    # Pick a random sample so the prompt stays short
    sample = random.sample(pool, min(25, len(pool)))
    sample_text = "\n".join(f"- {m}" for m in sample)

    profile = _profile_cache.get(user_id, "")
    profile_note = f"\n\nWhat you know about this user: {profile}" if profile else ""

    decision_prompt = (
        f"Someone replied to you with: \"{their_message}\"{profile_note}\n\n"
        f"Here are real messages group members have sent before:\n{sample_text}\n\n"
        f"Decide:\n"
        f"- If one of those messages above is a fitting, funny, or natural reply to what they said "
        f"→ output it VERBATIM, character for character, no changes at all.\n"
        f"- If none of them fit → write your own short reply in your usual style.\n\n"
        f"Output only the chosen message. No explanation, no prefix, nothing else."
    )

    try:
        resp = await groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": _build_system_prompt(user_id)},
                {"role": "user", "content": decision_prompt},
            ],
            model=_ai_model,
            max_tokens=256,
        )
        return (resp.choices[0].message.content or "…").strip()
    except Exception as e:
        logger.error(f"[ai_memory] reply_to_user error: {e}")
        return f"great, something broke. not my fault 😾\n`{str(e)[:120]}`"


async def personalized_tag(user_id: int, mention: str) -> str:
    """
    Generate a personalised tagging message for the random-tag feature.
    Falls back to a generic message if no profile is available yet.
    """
    await _ensure_profile_loaded(user_id)
    profile = _profile_cache.get(user_id, "")

    if not groq_client or not profile:
        return random.choice([
            f"oi {mention} where the hell have you been 😾",
            f"{mention} show your face already, you little gremlin 🐾",
            f"tch~ {mention} are you dead or just ignoring me? either way, rude 😾",
            f"what is WRONG with you {mention}, get in here 🐾",
            f"{mention} I swear to god if you don't respond I'm going to lose it 😾",
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
            model=_ai_model,
            max_tokens=120,
        )
        return (resp.choices[0].message.content or f"get over here {mention} 😾").strip()
    except Exception as e:
        logger.error(f"[ai_memory] personalized_tag error: {e}")
        return f"tch~ {mention} my brain died trying to think about you 😾"


def clear_history(user_id: int) -> None:
    """Wipe the conversation history for a user (profile is kept)."""
    _chat_history.pop(user_id, None)
