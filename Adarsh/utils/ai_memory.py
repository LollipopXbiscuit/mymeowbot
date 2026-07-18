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


# ── Question detection & answering ───────────────────────────────────────────

_Q_NAME = [
    r"اسمم\s*(چیه|چی\s*ه|رو\s*میدونی|یادته|چی\s*بود|چیست)",
    r"اسم\s*من\s*(چیه|چی\s*ه|رو\s*میدونی|یادته)",
    r"(میدونی|یادته)\s*(اسمم|اسم\s*من)",
    r"what[' ]?s?\s*my\s*name",
    r"what\s+is\s+my\s+name",
    r"do\s*you\s*know\s*my\s*name",
    r"remember\s*my\s*name",
    r"what\s*am\s*i\s*called",
]

_Q_LIKE = [
    r"چی\s*(دوست\s*دارم|خوشم\s*میاد)",
    r"(دوست\s*دارم\s*(چی|چیا)|علایقم\s*(چیه|چیا))",
    r"(میدونی|یادته)\s*(چی\s*دوست\s*دارم|علایقم)",
    r"what\s*do\s*i\s*(like|love|enjoy)",
    r"what\s*are\s*my\s*(likes|interests|favorites)",
]

_Q_DISLIKE = [
    r"از\s*چی\s*(بدم\s*میاد|متنفرم|خوشم\s*نمیاد)",
    r"(میدونی|یادته)\s*(از\s*چی\s*بدم\s*میاد|چی\s*(ازم|منو)\s*اذیت)",
    r"what\s*do\s*i\s*(hate|dislike|not\s*like)",
    r"what\s*are\s*my\s*(dislikes|hates)",
]

_Q_ABOUT = [
    r"(درباره|راجع\s*به)\s*(من|ازم)\s*(چی\s*میدونی|چی\s*یادته|چیا\s*بلدی)",
    r"منو\s*(میشناسی|یادته|یادت\s*میاد)",
    r"چی\s*(ازم|از\s*من)\s*(یادته|میدونی|بلدی)",
    r"what\s*do\s*you\s*know\s*about\s*me",
    r"do\s*you\s*(know|remember)\s*me",
    r"tell\s*me\s*what\s*you\s*know\s*about\s*me",
]

_Q_WORDS = [
    r"(پرتکرارترین|بیشترین)\s*(کلمه|کلمات|واژه)\s*(من|هام|هایم)",
    r"(most\s*used|frequent)\s*words?",
    r"what\s*words?\s*do\s*i\s*(use|say)\s*(most|a\s*lot)",
]


def _matches(text: str, patterns: list) -> bool:
    t = text.lower().strip()
    return any(re.search(p, t, re.IGNORECASE) for p in patterns)


_Q_FRIENDS = [
    r"دوستات\s*(کی(ا|ن|ان)|چی(ا|ن)|کیا\s*ن|کی\s*هستن)",
    r"(کیا|کی)\s*(تو\s*)?(حافظه|مموری|ذهن|یادت)\s*(داری|هستن|ات\s*هستن)",
    r"چند\s*(نفر|تا)\s*(تو\s*)?(حافظه|مموری|ذهنت)\s*(داری|هست)",
    r"(لیست\s*)?(دوستات|آدمایی\s*(که|رو)\s*(میشناسی|یادته|تو\s*حافظته))",
    r"کی\s*(رو\s*)?(میشناسی|یادته|یادت\s*هست)",
    r"who\s*are\s*your\s*friends",
    r"who\s*do\s*you\s*(know|remember)",
    r"list\s*(of\s*)?(your\s*)?(friends|people|users)",
]


def is_friends_question(text: str) -> bool:
    return _matches(text, _Q_FRIENDS)


async def list_friends() -> str:
    """Query DB for all stored memory profiles and return a formatted list."""
    try:
        profiles = await _db.get_all_memory_profiles()
    except Exception as e:
        return f"نتونستم از DB بخونم 😾 ({e})"

    if not profiles:
        return "هنوز کسی تو حافظه‌ام ثبت نشده 😾"

    lines = []
    for p in profiles:
        uid   = p.get("user_id", "?")
        name  = p.get("name") or "ناشناس"
        likes = p.get("likes", [])
        like_str = f" | دوست داره: {', '.join(likes[:2])}" if likes else ""
        lines.append(f"• {name} (ID: `{uid}`){like_str}")

    header = f"اینا آدمایی هستن که تو حافظمن ({len(profiles)} نفر) 😾\n\n"
    return header + "\n".join(lines)


def answer_question(user_id: int, text: str) -> str | None:
    """
    Check if the message is a memory question and answer it from the cache.
    Returns a reply string, or None if it's not a recognisable question.
    """
    mem = _cache.get(user_id, {})
    name     = mem.get("name")
    likes    = mem.get("likes", [])
    dislikes = mem.get("dislikes", [])
    words    = top_words(mem, 5)

    if _matches(text, _Q_NAME):
        if name:
            return random.choice([
                f"اسمت {name}ه 😾 فکر کردی فراموش کردم؟",
                f"tch~ {name}. معلومه دیگه 😾",
                f"your name is {name} — یادمه، نگران نباش 😾",
            ])
        return random.choice([
            "اسمتو بهم نگفتی که 😾 بگو تا یادم بمونه",
            "هنوز اسمتو ندونم 😾 بگو دیگه",
            "نگفتی اسمت چیه — بگو: «اسمم ... هست» 😾",
        ])

    if _matches(text, _Q_LIKE):
        if likes:
            listed = "، ".join(likes[:5])
            return random.choice([
                f"یادمه که دوست داری: {listed} 😾",
                f"tch~ اینا رو دوست داری: {listed}",
                f"علایقت: {listed} — یادم مونده 😾",
            ])
        return "هنوز نگفتی چی دوست داری 😾 بگو «دوست دارم ...»"

    if _matches(text, _Q_DISLIKE):
        if dislikes:
            listed = "، ".join(dislikes[:5])
            return random.choice([
                f"از اینا بدت میاد: {listed} 😾",
                f"tch~ گفتی از اینا متنفری: {listed}",
                f"دیسلایکات: {listed} — آره یادمه 😾",
            ])
        return "نگفتی از چی بدت میاد 😾 بگو «از ... متنفرم»"

    if _matches(text, _Q_ABOUT):
        parts = []
        if name:
            parts.append(f"اسمت: {name}")
        if likes:
            parts.append(f"دوست داری: {', '.join(likes[:3])}")
        if dislikes:
            parts.append(f"بدت میاد از: {', '.join(dislikes[:3])}")
        if words:
            parts.append(f"پرتکرارترین کلماتت: {', '.join(words)}")
        if parts:
            return "اینا رو ازت یادمه 😾\n" + "\n".join(f"• {p}" for p in parts)
        return "هنوز چیزی ازت یادم نگرفتم 😾 بیشتر حرف بزن"

    if _matches(text, _Q_WORDS):
        if words:
            return f"پرتکرارترین کلماتی که میگی: {', '.join(words)} 😾"
        return "هنوز کافی حرف نزدی که بفهمم 😾"

    return None


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
