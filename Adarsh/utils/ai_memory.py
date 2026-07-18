# user_memory.py — simple rule-based memory: no AI, no API keys needed.
# Tracks name / likes / dislikes / most-used words per user_id.

import re
import random
import logging
from collections import Counter

from Adarsh.vars import Var
from Adarsh.utils.database import Database

logger = logging.getLogger(__name__)

_db = Database(Var.DATABASE_URL, Var.name)

# In-memory cache  {user_id: dict}
_cache: dict[int, dict] = {}

# ── Stop-words (skip when counting frequent words) ───────────────────────────
_STOPWORDS = {
    # English
    "the", "a", "an", "is", "it", "i", "my", "me", "and", "or", "in",
    "on", "at", "to", "of", "for", "with", "that", "this", "are", "was",
    "be", "have", "has", "do", "did", "will", "can", "not", "but", "so",
    "you", "he", "she", "we", "they", "his", "her", "our", "their",
    # Persian
    "من", "تو", "او", "ما", "که", "را", "به", "در", "از", "با", "این",
    "آن", "هم", "هر", "یک", "ی", "می", "هست", "است", "بود", "هستم",
    "هستی", "شد", "شده", "داره", "داری", "دارم", "داریم",
}

# ── Detection patterns ────────────────────────────────────────────────────────
_NAME_PATTERNS = [
    r"(?:my name is|i'?m called|call me|i am)\s+([A-Za-z\u0600-\u06FF]{2,20})",
    r"(?:اسمم|اسم من)\s+([A-Za-z\u0600-\u06FF]{2,20})(?:\s*(?:هست|هستش|ه|است|میشه))?",
    r"(?:منو|مرا)\s+([A-Za-z\u0600-\u06FF]{2,20})\s+(?:صدا کن|بنام|صدا کنی)",
]

_LIKE_PATTERNS = [
    r"(?:i love|i like|i enjoy|i'm into|i adore)\s+(.{2,35}?)(?:\.|!|$|,|\n)",
    r"(?:دوست دارم|عاشقم|عاشق)\s+(.{2,30}?)(?:\.|!|$|,|\n|رو|را)",
    r"(.{2,30}?)\s+(?:رو دوست دارم|خوشم میاد|عالیه|بهترینه)",
]

_DISLIKE_PATTERNS = [
    r"(?:i hate|i dislike|i don't like|i can't stand)\s+(.{2,35}?)(?:\.|!|$|,|\n)",
    r"(?:از|ازِ)\s+(.{2,30}?)\s+(?:متنفرم|بدم میاد|خوشم نمیاد|حالم بهم میخوره)",
    r"(?:بدم میاد از|متنفرم از)\s+(.{2,30}?)(?:\.|!|$|,|\n)",
]


def _extract(text: str, patterns: list) -> list:
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            val = m.group(1).strip().strip(".,!?؟ ")
            if 2 <= len(val) <= 40:
                found.append(val.lower())
    return found


def _extract_name(text: str) -> str | None:
    for pat in _NAME_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip().capitalize()
            if 2 <= len(name) <= 20:
                return name
    return None


def _count_words(text: str) -> Counter:
    words = re.findall(r"[\w\u0600-\u06FF]{3,}", text.lower())
    return Counter(w for w in words if w not in _STOPWORDS)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _load(user_id: int) -> dict:
    if user_id in _cache:
        return _cache[user_id]
    doc = await _db.get_user_memory(user_id)
    mem = doc if doc else {
        "user_id": user_id,
        "name": None,
        "likes": [],
        "dislikes": [],
        "word_freq": {},
    }
    _cache[user_id] = mem
    return mem


async def _save(user_id: int, mem: dict):
    _cache[user_id] = mem
    await _db.save_user_memory(user_id, mem)


# ── Public API ────────────────────────────────────────────────────────────────

async def observe(user_id: int, text: str) -> None:
    """Feed a message into the user's memory profile."""
    if not text or len(text.strip()) < 2:
        return

    mem = await _load(user_id)
    changed = False

    # Name detection
    if not mem["name"]:
        name = _extract_name(text)
        if name:
            mem["name"] = name
            changed = True
            logger.info(f"[memory] Learned name '{name}' for user {user_id}")

    # Likes
    for item in _extract(text, _LIKE_PATTERNS):
        if item not in mem["likes"]:
            mem["likes"] = (mem["likes"] + [item])[-20:]
            changed = True

    # Dislikes
    for item in _extract(text, _DISLIKE_PATTERNS):
        if item not in mem["dislikes"]:
            mem["dislikes"] = (mem["dislikes"] + [item])[-20:]
            changed = True

    # Word frequency (always update)
    freq = mem.get("word_freq", {})
    for word, n in _count_words(text).items():
        freq[word] = freq.get(word, 0) + n
    mem["word_freq"] = dict(Counter(freq).most_common(50))
    changed = True

    if changed:
        await _save(user_id, mem)


async def get_memory(user_id: int) -> dict:
    """Return the full memory profile for a user."""
    return await _load(user_id)


def top_words(mem: dict, n: int = 5) -> list:
    return [w for w, _ in Counter(mem.get("word_freq", {})).most_common(n)]


# ── Template-based reply builder ──────────────────────────────────────────────

_GREET_NAME = [
    "اوه، {name} اومد 😾",
    "ها؟ {name} چی میخوای",
    "tch~ {name}...",
    "{name} باز اینجایی؟",
    "اوه {name} دوباره؟ 😾",
]
_GREET_ANON = [
    "ها؟ چی میخوای 😾",
    "tch~ چیه باز",
    "بگو چی میخوای",
    "اومدی چیکار 😾",
]
_LIKE_REPLY = [
    "اوه پس {item} دوست داری... جالبه 😾",
    "tch~ {item}؟ انتظار بهتری نداشتم",
    "خب بیخود دوست داری {item} رو 😾",
]
_DISLIKE_REPLY = [
    "از {item} بدت میاد؟ عاقبت یه چیز درستی گفتی 😾",
    "tch~ {item}؟ منم همینطور 😾",
    "آره {item} واقعاً مزخرفه 😾",
]
_WORD_REPLY = [
    'هنوزم "{word}" میگی؟ 😾',
    'tch~ "{word}" دیگه چی 😾',
]
_GENERIC = [
    "چیه باز 😾",
    "tch~ 😾",
    "هوووف 😾",
    "خب؟ 😾",
    "ادامه بده 😾",
    "بله؟ 😾",
]


def build_reply(user_id: int, their_text: str = "") -> str:
    """Build a personalised reply from stored memory — no API needed."""
    mem = _cache.get(user_id, {})
    name    = mem.get("name")
    likes   = mem.get("likes", [])
    dislikes = mem.get("dislikes", [])
    words   = top_words(mem, 5)

    pool = []

    if name:
        pool += [t.format(name=name) for t in _GREET_NAME]
    else:
        pool += _GREET_ANON[:]

    if likes and random.random() < 0.4:
        pool.append(random.choice(_LIKE_REPLY).format(item=random.choice(likes)))

    if dislikes and random.random() < 0.4:
        pool.append(random.choice(_DISLIKE_REPLY).format(item=random.choice(dislikes)))

    if words and their_text:
        for word in words:
            if word in their_text.lower():
                pool.append(random.choice(_WORD_REPLY).format(word=word))
                break

    pool += _GENERIC
    return random.choice(pool)


# ── Tag builder ───────────────────────────────────────────────────────────────

_TAG_NAME = [
    "oi {name}! {mention} کجایی؟ 😾",
    "{name}! {mention} بیا اینجا 🐾",
    "tch~ {name} {mention} غیبت زده؟ 😾",
    "{mention} ({name}) شنیدی یا نه؟ 😾",
]
_TAG_LIKE = [
    "{mention} برو {item} بخر خودتو مشغول کن 😾",
    "هی {mention} فکر کردم بری دنبال {item} گم شدی 😾",
]
_TAG_GENERIC = [
    "oi {mention} کجا رفتی؟ 😾",
    "{mention} شنیدی یا نه؟ 🐾",
    "tch~ {mention} بیا اینجا 😾",
    "{mention} مردی؟ 😾",
    "هی {mention}! 🐾",
]


def build_tag(user_id: int, mention: str) -> str:
    """Build a personalised tag message from stored memory."""
    mem   = _cache.get(user_id, {})
    name  = mem.get("name")
    likes = mem.get("likes", [])

    pool = []

    if name:
        pool += [t.format(name=name, mention=mention) for t in _TAG_NAME]

    if likes:
        item = random.choice(likes)
        pool += [t.format(mention=mention, item=item) for t in _TAG_LIKE]

    pool += [t.format(mention=mention) for t in _TAG_GENERIC]
    return random.choice(pool)
