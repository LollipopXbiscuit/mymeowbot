# ai_memory.py — advanced rule-based memory system (no external AI)
# Tracks: name / likes / dislikes / mood / topics / message count / last quote

import re
import random
import logging
import time
from collections import Counter

from Adarsh.vars import Var
from Adarsh.utils.database import Database

logger = logging.getLogger(__name__)

_db = Database(Var.DATABASE_URL, Var.name)

# In-memory cache  {user_id: dict}
_cache: dict[int, dict] = {}

# ── Stop-words ────────────────────────────────────────────────────────────────
_STOPWORDS = {
    "the", "a", "an", "is", "it", "i", "my", "me", "and", "or", "in",
    "on", "at", "to", "of", "for", "with", "that", "this", "are", "was",
    "be", "have", "has", "do", "did", "will", "can", "not", "but", "so",
    "you", "he", "she", "we", "they", "his", "her", "our", "their",
    "\u0645\u0646", "\u062a\u0648", "\u0627\u0648", "\u0645\u0627",
    "\u06a9\u0647", "\u0631\u0627", "\u0628\u0647", "\u062f\u0631",
    "\u0627\u0632", "\u0628\u0627", "\u0627\u06cc\u0646", "\u0622\u0646",
    "\u0647\u0645", "\u0647\u0631", "\u06cc\u06a9", "\u06cc",
    "\u0645\u06cc", "\u0647\u0633\u062a", "\u0627\u0633\u062a",
    "\u0628\u0648\u062f", "\u0647\u0633\u062a\u0645",
    "\u0647\u0633\u062a\u06cc", "\u0634\u062f", "\u0634\u062f\u0647",
    "\u062f\u0627\u0631\u0647", "\u062f\u0627\u0631\u06cc",
    "\u062f\u0627\u0631\u0645", "\u062f\u0627\u0631\u06cc\u0645",
}

# ── Topic keywords ─────────────────────────────────────────────────────────────
_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "\u0645\u0648\u0633\u06cc\u0642\u06cc": [
        r"\u0645\u0648\u0633\u06cc\u0642\u06cc|\u0622\u0647\u0646\u06af|\u06af\u06cc\u062a\u0627\u0631|\u067e\u06cc\u0627\u0646\u0648|\u0633\u0627\u0632|music|song|playlist|spotify|rap|pop|rock"
    ],
    "\u06af\u06cc\u0645\u06cc\u0646\u06af": [
        r"\u0628\u0627\u0632\u06cc|\u06af\u06cc\u0645|\u067e\u0644\u06cc\u200c\u0627\u0633\u062a\u06cc\u0634\u0646|ps[45]|xbox|gaming|game|steam|valorant|\u0641\u0648\u0631\u062a\u0646\u0627\u06cc\u062a|minecraft"
    ],
    "\u0648\u0631\u0632\u0634": [
        r"\u0648\u0631\u0632\u0634|\u0641\u0648\u062a\u0628\u0627\u0644|\u0628\u0633\u06a9\u062a\u0628\u0627\u0644|\u062a\u0646\u06cc\u0633|\u0628\u0627\u0634\u06af\u0627\u0647|gym|workout|sport|football|running"
    ],
    "\u063a\u0630\u0627": [
        r"\u063a\u0630\u0627|\u062e\u0648\u0631\u0627\u06a9\u06cc|\u0622\u0634\u067e\u0632\u06cc|\u0631\u0633\u062a\u0648\u0631\u0627\u0646|\u067e\u06cc\u062a\u0632\u0627|food|cook|eat|restaurant|\u0633\u0648\u0634\u06cc"
    ],
    "\u062f\u0631\u0633": [
        r"\u062f\u0631\u0633|\u0645\u062f\u0631\u0633\u0647|\u062f\u0627\u0646\u0634\u06af\u0627\u0647|\u0627\u0645\u062a\u062d\u0627\u0646|\u06a9\u0646\u06a9\u0648\u0631|study|school|university|homework|exam"
    ],
    "\u062a\u06a9\u0646\u0648\u0644\u0648\u0698\u06cc": [
        r"\u062a\u06a9\u0646\u0648\u0644\u0648\u0698\u06cc|\u06af\u0648\u0634\u06cc|\u0644\u067e\u200c\u062a\u0627\u067e|\u06a9\u0627\u0645\u067e\u06cc\u0648\u062a\u0631|\u06a9\u062f\u0646\u0648\u06cc\u0633\u06cc|\u0628\u0631\u0646\u0627\u0645\u0647\u200c\u0646\u0648\u06cc\u0633\u06cc|tech|phone|laptop|coding|python|ai"
    ],
    "\u0641\u06cc\u0644\u0645": [
        r"\u0641\u06cc\u0644\u0645|\u0633\u0631\u06cc\u0627\u0644|\u0633\u06cc\u0646\u0645\u0627|\u0646\u062a\u0641\u0644\u06cc\u06a9\u0633|movie|series|netflix|cinema|anime|cartoon"
    ],
    "\u0633\u0641\u0631": [
        r"\u0633\u0641\u0631|\u0645\u0633\u0627\u0641\u0631\u062a|\u06af\u0631\u062f\u0634|\u06a9\u0634\u0648\u0631|\u0634\u0647\u0631|travel|trip|vacation|abroad"
    ],
}

# ── Detection patterns ────────────────────────────────────────────────────────

_NAME_PATTERNS = [
    r"(?:my name is|i'?m called|call me|i am)\s+([A-Za-z\u0600-\u06FF]{2,20})",
    r"(?:\u0627\u0633\u0645\u0645|\u0627\u0633\u0645 \u0645\u0646)\s+([A-Za-z\u0600-\u06FF]{2,20})(?:\s*(?:\u0647\u0633\u062a|\u0647\u0633\u062a\u0634|\u0647|\u0627\u0633\u062a|\u0645\u06cc\u0634\u0647))?",
    r"(?:\u0645\u0646\u0648|\u0645\u0631\u0627)\s+([A-Za-z\u0600-\u06FF]{2,20})\s+(?:\u0635\u062f\u0627 \u06a9\u0646|\u0628\u0646\u0627\u0645|\u0635\u062f\u0627 \u06a9\u0646\u06cc)",
]

_NAME_CORRECTION_PATTERNS = [
    r"\u0646\u0647[،!\s]*\u0627\u0633\u0645(?:\u0645|\s*\u0645\u0646)\s+([A-Za-z\u0600-\u06FF]{2,20})\s+(?:\u0647\u0633\u062a|\u0647|\u0647\u0633\u062a\u0634)(?:\s+\u0646\u0647)?",
    r"\u0627\u0633\u0645(?:\u0645|\s*\u0645\u0646)\s+([A-Za-z\u0600-\u06FF]{2,20})\s+\u0647\u0633\u062a\s+\u0646\u0647",
    r"no[,!]?\s+my name is\s+([A-Za-z\u0600-\u06FF]{2,20})\s+not",
    r"my name is\s+([A-Za-z\u0600-\u06FF]{2,20})\s+not",
]

_LIKE_PATTERNS = [
    r"(?:i love|i like|i enjoy|i'm into|i adore)\s+(.{2,40}?)(?:\.|!|$|,|\n)",
    r"(?:\u062f\u0648\u0633\u062a \u062f\u0627\u0631\u0645|\u0639\u0627\u0634\u0642\u0645|\u0639\u0627\u0634\u0642)\s+(.{2,40}?)(?:\.|!|$|,|\n|\u0631\u0648|\u0631\u0627)",
    r"(.{2,30}?)\s+(?:\u0631\u0648 \u062f\u0648\u0633\u062a \u062f\u0627\u0631\u0645|\u062e\u0648\u0634\u0645 \u0645\u06cc\u0627\u062f|\u0639\u0627\u0644\u06cc\u0647|\u0628\u0647\u062a\u0631\u06cc\u0646\u0647)",
]

_DISLIKE_PATTERNS = [
    r"(?:i hate|i dislike|i don't like|i can't stand)\s+(.{2,40}?)(?:\.|!|$|,|\n)",
    r"(?:\u0627\u0632|\u0627\u0632\u0650)\s+(.{2,35}?)\s+(?:\u0645\u062a\u0646\u0641\u0631\u0645|\u0628\u062f\u0645 \u0645\u06cc\u0627\u062f|\u062e\u0648\u0634\u0645 \u0646\u0645\u06cc\u0627\u062f|\u062d\u0627\u0644\u0645 \u0628\u0647\u0645 \u0645\u06cc\u062e\u0648\u0631\u0647)",
    r"(?:\u0628\u062f\u0645 \u0645\u06cc\u0627\u062f \u0627\u0632|\u0645\u062a\u0646\u0641\u0631\u0645 \u0627\u0632)\s+(.{2,35}?)(?:\.|!|$|,|\n)",
]

# Remove from likes + add to dislikes
_UNLIKE_PATTERNS = [
    r"(?:\u062f\u06cc\u06af\u0647|\u062f\u06cc\u06af\u0631)\s+(.{2,30}?)\s+(?:\u0631\u0648|\u0631\u0627)\s+\u062f\u0648\u0633\u062a\s+(?:\u0646\u062f\u0627\u0631\u0645|\u0646\u062f\u0627\u0631\u062f)",
    r"(?:\u062f\u06cc\u06af\u0647|\u062f\u06cc\u06af\u0631)\s+(?:\u0627\u0632\s+)?(.{2,30}?)\s+\u062e\u0648\u0634\u0645\s+\u0646\u0645\u06cc\u0627\u062f",
    r"i\s+(?:no longer|don'?t|do not)\s+(?:like|love)\s+(.{2,35}?)(?:\.|!|$|,|\n)",
]

_MOOD_PATTERNS: dict[str, list[str]] = {
    "\u062e\u0648\u0634\u062d\u0627\u0644": [
        r"\u062e\u0648\u0634\u062d\u0627\u0644\u0645|\u062d\u0627\u0644\u0645 \u062e\u0648\u0628\u0647|\u0627\u0645\u0631\u0648\u0632 \u062e\u0648\u0628\u0645|\u0639\u0627\u0644\u06cc|\u0634\u0627\u062f\u0645|i'?m happy|feeling good|great day|so happy|\u0627\u0645\u0631\u0648\u0632 \u0639\u0627\u0644\u06cc\u0647|\u062d\u0627\u0644\u0645 \u062e\u06cc\u0644\u06cc \u062e\u0648\u0628\u0647",
    ],
    "\u0646\u0627\u0631\u0627\u062d\u062a": [
        r"\u0646\u0627\u0631\u0627\u062d\u062a\u0645|\u062f\u0644\u0645 \u06af\u0631\u0641\u062a\u0647|\u063a\u0645\u06af\u06cc\u0646\u0645|\u062d\u0627\u0644\u0645 \u062e\u0648\u0628 \u0646\u06cc\u0633\u062a|\u0627\u0641\u0633\u0631\u062f\u0647|i'?m sad|feeling (?:down|low|blue)|i feel bad",
    ],
    "\u0639\u0635\u0628\u0627\u0646\u06cc": [
        r"\u0639\u0635\u0628\u0627\u0646\u06cc\u0645|\u062d\u0631\u0635\u0645 \u06af\u0631\u0641\u062a\u0647|\u0639\u0635\u0628\u06cc\u0645|\u062f\u0627\u0631\u06cc \u062f\u06cc\u0648\u0648\u0646\u0645 \u0645\u06cc\u06a9\u0646\u06cc|i'?m angry|so frustrated|pissed off|\u062d\u0631\u0635\u0645 \u062f\u0631 \u0627\u0648\u0645\u062f",
    ],
    "\u0628\u06cc\u200c\u062d\u0648\u0635\u0644\u0647": [
        r"\u062d\u0648\u0635\u0644\u0645 \u0633\u0631 \u0631\u0641\u062a\u0647|\u06a9\u0633\u0644\u0645|\u0628\u06cc\u200c\u062d\u0648\u0635\u0644\u0647\u200c\u0627\u0645|boring|i'?m bored|nothing to do|\u06a9\u0627\u0631\u06cc \u0646\u062f\u0627\u0631\u0645",
    ],
    "\u062e\u0633\u062a\u0647": [
        r"\u062e\u0633\u062a\u0647\u200c\u0627\u0645|\u062e\u0633\u062a\u0645|\u06a9\u0648\u0641\u062a\u0647\u200c\u0627\u0645|i'?m tired|exhausted|so tired|\u062e\u06cc\u0644\u06cc \u062e\u0633\u062a\u0645",
    ],
    "\u0647\u06cc\u062c\u0627\u0646\u200c\u0632\u062f\u0647": [
        r"\u0647\u06cc\u062c\u0627\u0646 \u0632\u062f\u0645|\u0646\u0645\u06cc\u200c\u062a\u0648\u0646\u0645 \u0635\u0628\u0631 \u06a9\u0646\u0645|so excited|can'?t wait|\u0647\u06cc\u062c\u0627\u0646\u06cc\u0645",
    ],
}

_BIRTHDAY_PATTERNS = [
    r"(?:\u0627\u0645\u0631\u0648\u0632\s+)?\u062a\u0648\u0644\u062f\u0645\u0647|\u062a\u0648\u0644\u062f\u0645\s+(?:\u0627\u0645\u0631\u0648\u0632\u0647|\u0647\u0633\u062a|\u0647\u0633\u062a\u0634)",
    r"today\s+is\s+my\s+birthday|it'?s\s+my\s+birthday",
    r"my\s+birthday\s+(is\s+)?today",
]

_NAME_BLOCKLIST = {
    "\u0686\u06cc\u0647", "\u0686\u06cc\u0633\u062a", "\u0686\u06cc", "\u0686\u06cc\u0627",
    "\u06a9\u06cc\u0647", "\u06a9\u06cc\u0633\u062a", "\u06a9\u06cc", "\u0686\u06cc\u0648", "\u0686\u06cc\u0645",
    "\u0647\u0633\u062a", "\u0647\u0633\u062a\u0634", "\u0647\u0633\u062a\u0645", "\u0647\u0633\u062a\u06cc",
    "\u0647", "\u0627\u06cc", "\u0627\u0633\u062a", "\u0628\u0627\u0634\u0647", "\u0628\u0648\u062f",
    "\u0645\u06cc\u0634\u0647", "\u0646\u06cc\u0633\u062a", "\u0646\u0647", "\u0622\u0631\u0647", "\u0628\u0644\u0647", "\u0627\u0631\u0647",
    "not", "yes", "no", "called", "am", "is", "are", "been",
}


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _extract_name(text: str) -> str | None:
    for pat in _NAME_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip().capitalize()
            if 2 <= len(name) <= 20 and name.lower() not in _NAME_BLOCKLIST:
                return name
    return None


def _extract_name_correction(text: str) -> str | None:
    for pat in _NAME_CORRECTION_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip().capitalize()
            if 2 <= len(name) <= 20:
                return name
    return None


def _extract(text: str, patterns: list) -> list:
    """Extract items; split each on standalone و / and / , so multi-item phrases store separately.
    Only splits on و surrounded by whitespace to avoid chopping inside words like موسیقی."""
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            raw = m.group(1).strip().strip(".,!?\u061f ")
            # Split on whitespace-bounded و, commas, or ' and '
            for part in re.split(r'\s+\u0648\s+|\s*,\s*|\s+and\s+', raw):
                part = part.strip().strip(".,!?\u061f ")
                if 2 <= len(part) <= 35:
                    found.append(part.lower())
    return list(dict.fromkeys(found))  # deduplicate, keep order


def _detect_mood(text: str) -> str | None:
    t = text.lower()
    for mood, pats in _MOOD_PATTERNS.items():
        for p in pats:
            if re.search(p, t, re.IGNORECASE):
                return mood
    return None


def _detect_birthday(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _BIRTHDAY_PATTERNS)


def _detect_topics(text: str) -> list:
    found = []
    t = text.lower()
    for topic, pats in _TOPIC_KEYWORDS.items():
        if any(re.search(p, t, re.IGNORECASE) for p in pats):
            found.append(topic)
    return found


def _count_words(text: str) -> Counter:
    words = re.findall(r"[\w\u0600-\u06FF]{3,}", text.lower())
    return Counter(w for w in words if w not in _STOPWORDS)


def _extract_emojis(text: str) -> list[str]:
    return re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", text)


def _extract_phrases(text: str) -> list[str]:
    """Return repeated-speech candidates without storing whole messages."""
    words = re.findall(r"[A-Za-z\u0600-\u06FF]{2,}", text.lower())
    phrases = []
    for size in (2, 3):
        for index in range(len(words) - size + 1):
            phrase_words = words[index:index + size]
            if all(word not in _STOPWORDS for word in phrase_words):
                phrases.append(" ".join(phrase_words))
    return phrases


def _is_quotable(text: str) -> bool:
    t = text.strip()
    if len(t) < 15 or t.endswith('\u061f') or t.endswith('?'):
        return False
    if re.match(r'^[/!]', t):
        return False
    return True


def _familiarity(mem: dict) -> str:
    count = mem.get("msg_count", 0)
    if count < 10:
        return "new"
    if count < 50:
        return "regular"
    return "friend"


def _message_style(mem: dict) -> str:
    average_length = float(mem.get("avg_msg_length", 0) or 0)
    if average_length and average_length < 35:
        return "short"
    if average_length > 100:
        return "long"
    return "balanced"


# ── DB helpers ────────────────────────────────────────────────────────────────

def _empty_profile(user_id: int) -> dict:
    return {
        "user_id": user_id,
        "name": None,
        "likes": [],
        "dislikes": [],
        "word_freq": {},
        "mood": None,
        "mood_ts": None,
        "msg_count": 0,
        "last_quote": None,
        "birthday_mentioned": False,
        "topics": [],
        "emoji_freq": {},
        "phrase_freq": {},
        "avg_msg_length": 0,
        "question_count": 0,
        "exclamation_count": 0,
    }


async def _load(user_id: int) -> dict:
    if user_id in _cache:
        return _cache[user_id]
    doc = await _db.get_user_memory(user_id)
    mem = doc if doc else _empty_profile(user_id)
    for k, v in _empty_profile(user_id).items():
        mem.setdefault(k, v)
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

    # Message counter and communication style
    previous_count = mem.get("msg_count", 0)
    mem["msg_count"] = previous_count + 1
    message_length = len(text.strip())
    previous_average = float(mem.get("avg_msg_length", 0) or 0)
    mem["avg_msg_length"] = round(
        ((previous_average * previous_count) + message_length) / mem["msg_count"],
        1,
    )
    if "?" in text or "\u061f" in text:
        mem["question_count"] = mem.get("question_count", 0) + 1
    if "!" in text:
        mem["exclamation_count"] = mem.get("exclamation_count", 0) + 1

    # Name correction (overrides whatever was stored)
    correction = _extract_name_correction(text)
    if correction:
        old = mem.get("name")
        mem["name"] = correction
        logger.info(f"[memory] Corrected name '{old}' \u2192 '{correction}' for user {user_id}")
    elif not mem["name"]:
        name = _extract_name(text)
        if name:
            mem["name"] = name
            logger.info(f"[memory] Learned name '{name}' for user {user_id}")

    # Likes (multi-item split)
    for item in _extract(text, _LIKE_PATTERNS):
        if item not in mem["likes"]:
            mem["likes"] = (mem["likes"] + [item])[-30:]

    # Unlike (remove from likes, add to dislikes)
    for item in _extract(text, _UNLIKE_PATTERNS):
        mem["likes"] = [l for l in mem["likes"] if l != item]
        if item not in mem["dislikes"]:
            mem["dislikes"] = (mem["dislikes"] + [item])[-30:]

    # Dislikes (multi-item split)
    for item in _extract(text, _DISLIKE_PATTERNS):
        if item not in mem["dislikes"]:
            mem["dislikes"] = (mem["dislikes"] + [item])[-30:]

    # Mood
    mood = _detect_mood(text)
    if mood:
        mem["mood"] = mood
        mem["mood_ts"] = int(time.time())
        logger.info(f"[memory] Detected mood '{mood}' for user {user_id}")

    # Birthday
    if _detect_birthday(text):
        mem["birthday_mentioned"] = True

    # Topics
    for topic in _detect_topics(text):
        if topic not in mem.get("topics", []):
            mem["topics"] = (mem.get("topics", []) + [topic])[-10:]

    # Last notable quote
    if _is_quotable(text):
        mem["last_quote"] = text[:120]

    # Word frequency
    freq = mem.get("word_freq", {})
    for word, n in _count_words(text).items():
        freq[word] = freq.get(word, 0) + n
    mem["word_freq"] = dict(Counter(freq).most_common(50))

    # Emoji and repeated phrase habits
    emoji_freq = mem.get("emoji_freq", {})
    for emoji in _extract_emojis(text):
        emoji_freq[emoji] = emoji_freq.get(emoji, 0) + 1
    mem["emoji_freq"] = dict(Counter(emoji_freq).most_common(12))

    phrase_freq = mem.get("phrase_freq", {})
    for phrase in _extract_phrases(text):
        phrase_freq[phrase] = phrase_freq.get(phrase, 0) + 1
    mem["phrase_freq"] = dict(Counter(phrase_freq).most_common(20))

    await _save(user_id, mem)


async def get_memory(user_id: int) -> dict:
    return await _load(user_id)


def top_words(mem: dict, n: int = 5) -> list:
    return [w for w, _ in Counter(mem.get("word_freq", {})).most_common(n)]


# ── Question detection & answering ────────────────────────────────────────────

_Q_NAME = [
    r"\u0627\u0633\u0645\u0645\s*(\u0686\u06cc\u0647|\u0686\u06cc\s*\u0647|\u0631\u0648\s*\u0645\u06cc\u062f\u0648\u0646\u06cc|\u06cc\u0627\u062f\u062a\u0647|\u0686\u06cc\s*\u0628\u0648\u062f|\u0686\u06cc\u0633\u062a)",
    r"\u0627\u0633\u0645\s*\u0645\u0646\s*(\u0686\u06cc\u0647|\u0686\u06cc\s*\u0647|\u0631\u0648\s*\u0645\u06cc\u062f\u0648\u0646\u06cc|\u06cc\u0627\u062f\u062a\u0647)",
    r"(\u0645\u06cc\u062f\u0648\u0646\u06cc|\u06cc\u0627\u062f\u062a\u0647)\s*(\u0627\u0633\u0645\u0645|\u0627\u0633\u0645\s*\u0645\u0646)",
    r"what[' ]?s?\s*my\s*name",
    r"what\s+is\s+my\s+name",
    r"do\s*you\s*know\s*my\s*name",
    r"remember\s*my\s*name",
    r"what\s*am\s*i\s*called",
]

_Q_LIKE = [
    r"\u0686\u06cc\s*(\u062f\u0648\u0633\u062a\s*\u062f\u0627\u0631\u0645|\u062e\u0648\u0634\u0645\s*\u0645\u06cc\u0627\u062f)",
    r"(\u062f\u0648\u0633\u062a\s*\u062f\u0627\u0631\u0645\s*(\u0686\u06cc|\u0686\u06cc\u0627)|\u0639\u0644\u0627\u06cc\u0642\u0645\s*(\u0686\u06cc\u0647|\u0686\u06cc\u0627))",
    r"(\u0645\u06cc\u062f\u0648\u0646\u06cc|\u06cc\u0627\u062f\u062a\u0647)\s*(\u0686\u06cc\s*\u062f\u0648\u0633\u062a\s*\u062f\u0627\u0631\u0645|\u0639\u0644\u0627\u06cc\u0642\u0645)",
    r"what\s*do\s*i\s*(like|love|enjoy)",
    r"what\s*are\s*my\s*(likes|interests|favorites)",
]

_Q_DISLIKE = [
    r"\u0627\u0632\s*\u0686\u06cc\s*(\u0628\u062f\u0645\s*\u0645\u06cc\u0627\u062f|\u0645\u062a\u0646\u0641\u0631\u0645|\u062e\u0648\u0634\u0645\s*\u0646\u0645\u06cc\u0627\u062f)",
    r"(\u0645\u06cc\u062f\u0648\u0646\u06cc|\u06cc\u0627\u062f\u062a\u0647)\s*(\u0627\u0632\s*\u0686\u06cc\s*\u0628\u062f\u0645\s*\u0645\u06cc\u0627\u062f|\u0686\u06cc\s*(\u0627\u0632\u0645|\u0645\u0646\u0648)\s*\u0627\u0630\u06cc\u062a)",
    r"what\s*do\s*i\s*(hate|dislike|not\s*like)",
    r"what\s*are\s*my\s*(dislikes|hates)",
]

_Q_MOOD = [
    r"\u062d\u0627\u0644\u0645\s*(\u0686\u0637\u0648\u0631\u0647|\u0686\u0637\u0648\u0631\s*\u0628\u0648\u062f|\u062e\u0648\u0628\u0647|\u0628\u062f\u0647)\s*(\u0628\u0647\s*\u0646\u0638\u0631\u062a)?",
    r"(\u0641\u06a9\u0631\s*\u0645\u06cc\u06a9\u0646\u06cc|\u062d\u0633\s*\u0645\u06cc\u06a9\u0646\u06cc)\s*(\u062d\u0627\u0644\u0645|\u0631\u0648\u062d\u06cc\u0647\u200c\u0627\u0645)\s*(\u0686\u0637\u0648\u0631\u0647|\u062e\u0648\u0628\u0647|\u0628\u062f\u0647)",
    r"(\u0645\u06cc\u062f\u0648\u0646\u06cc|\u06cc\u0627\u062f\u062a\u0647)\s*(\u062d\u0627\u0644\u0645|\u0631\u0648\u062d\u06cc\u0647\u200c\u0627\u0645)\s*(\u0686\u0637\u0648\u0631 \u0628\u0648\u062f|\u0686\u0637\u0648\u0631\u0647)",
    r"what'?s?\s*my\s*(mood|vibe)",
    r"how\s*(do\s*i\s*seem|am\s*i\s*(feeling|doing))",
]

_Q_TOPICS = [
    r"\u0628\u06cc\u0634\u062a\u0631\s*(?:\u062f\u0631\u0628\u0627\u0631\u0647|\u0631\u0627\u062c\u0639\s*\u0628\u0647)\s*\u0686\u06cc\s*(?:\u062d\u0631\u0641\s*\u0632\u062f\u0645|\u0635\u062d\u0628\u062a\s*\u06a9\u0631\u062f\u0645)",
    r"\u0686\u06cc\s*(?:\u0628\u0627\u0647\u0627\u062a|\u0628\u0627\s*\u062a\u0648)\s*(?:\u062d\u0631\u0641|\u0635\u062d\u0628\u062a)\s*\u0632\u062f\u0645",
    r"\u0645\u0648\u0636\u0648\u0639\s*\u0645\u0648\u0631\u062f\s*\u0639\u0644\u0627\u0642\u0647",
    r"what\s*(topics?|subjects?)\s*do\s*i\s*(talk|care)\s*about",
    r"what\s*are\s*my\s*(interests|topics|hobbies)",
]

_Q_ABOUT = [
    r"(\u062f\u0631\u0628\u0627\u0631\u0647|\u0631\u0627\u062c\u0639\s*\u0628\u0647)\s*(\u0645\u0646|\u0627\u0632\u0645)\s*(\u0686\u06cc\s*\u0645\u06cc\u062f\u0648\u0646\u06cc|\u0686\u06cc\s*\u06cc\u0627\u062f\u062a\u0647|\u0686\u06cc\u0627\s*\u0628\u0644\u062f\u06cc)",
    r"\u0645\u0646\u0648\s*(\u0645\u06cc\u0634\u0646\u0627\u0633\u06cc|\u06cc\u0627\u062f\u062a\u0647|\u06cc\u0627\u062f\u062a \u0645\u06cc\u0627\u062f)",
    r"\u0686\u06cc\s*(\u0627\u0632\u0645|\u0627\u0632\s*\u0645\u0646)\s*(\u06cc\u0627\u062f\u062a\u0647|\u0645\u06cc\u062f\u0648\u0646\u06cc|\u0628\u0644\u062f\u06cc)",
    r"what\s*do\s*you\s*know\s*about\s*me",
    r"do\s*you\s*(know|remember)\s*me",
    r"tell\s*me\s*what\s*you\s*know\s*about\s*me",
]

_Q_WORDS = [
    r"(\u067e\u0631\u062a\u06a9\u0631\u0627\u0631\u062a\u0631\u06cc\u0646|\u0628\u06cc\u0634\u062a\u0631\u06cc\u0646)\s*(\u06a9\u0644\u0645\u0647|\u06a9\u0644\u0645\u0627\u062a|\u0648\u0627\u0698\u0647)\s*(\u0645\u0646|\u0647\u0627\u0645|\u0647\u0627\u06cc\u0645)",
    r"(most\s*used|frequent)\s*words?",
    r"what\s*words?\s*do\s*i\s*(use|say)\s*(most|a\s*lot)",
]


def _matches(text: str, patterns: list) -> bool:
    t = text.lower().strip()
    return any(re.search(p, t, re.IGNORECASE) for p in patterns)


_Q_FRIENDS = [
    r"\u062f\u0648\u0633\u062a\u0627\u062a\s*(\u06a9\u06cc(\u0627|\u0646|\u0627\u0646)|\u0686\u06cc(\u0627|\u0646)|\u06a9\u06cc\u0627\s*\u0646|\u06a9\u06cc\s*\u0647\u0633\u062a\u0646)",
    r"(\u06a9\u06cc\u0627|\u06a9\u06cc)\s*(\u062a\u0648\s*)?(\u062d\u0627\u0641\u0638\u0647|\u0645\u0645\u0648\u0631\u06cc|\u0630\u0647\u0646|\u06cc\u0627\u062f\u062a)\s*(\u062f\u0627\u0631\u06cc|\u0647\u0633\u062a\u0646|\u0627\u062a\s*\u0647\u0633\u062a\u0646)",
    r"\u0686\u0646\u062f\s*(\u0646\u0641\u0631|\u062a\u0627)\s*(\u062a\u0648\s*)?(\u062d\u0627\u0641\u0638\u0647|\u0645\u0645\u0648\u0631\u06cc|\u0630\u0647\u0646\u062a)\s*(\u062f\u0627\u0631\u06cc|\u0647\u0633\u062a)",
    r"(\u0644\u06cc\u0633\u062a\s*)?(\u062f\u0648\u0633\u062a\u0627\u062a|\u0622\u062f\u0645\u0627\u06cc\u06cc\s*(\u06a9\u0647|\u0631\u0648)\s*(\u0645\u06cc\u0634\u0646\u0627\u0633\u06cc|\u06cc\u0627\u062f\u062a\u0647|\u062a\u0648\s*\u062d\u0627\u0641\u0638\u062a\u0647))",
    r"\u06a9\u06cc\s*(\u0631\u0648\s*)?(\u0645\u06cc\u0634\u0646\u0627\u0633\u06cc|\u06cc\u0627\u062f\u062a\u0647|\u06cc\u0627\u062f\u062a\s*\u0647\u0633\u062a)",
    r"who\s*are\s*your\s*friends",
    r"who\s*do\s*you\s*(know|remember)",
    r"list\s*(of\s*)?(your\s*)?(friends|people|users)",
]


def is_friends_question(text: str) -> bool:
    return _matches(text, _Q_FRIENDS)


async def list_friends() -> str:
    try:
        profiles = await _db.get_all_memory_profiles()
    except Exception as e:
        return f"\u0646\u062a\u0648\u0646\u0633\u062a\u0645 \u0627\u0632 DB \u0628\u062e\u0648\u0646\u0645 \U0001f63e ({e})"

    if not profiles:
        return "\u0647\u0646\u0648\u0632 \u06a9\u0633\u06cc \u062a\u0648 \u062d\u0627\u0641\u0638\u0647\u200c\u0627\u0645 \u062b\u0628\u062a \u0646\u0634\u062f\u0647 \U0001f63e"

    lines = []
    for p in profiles:
        uid    = p.get("user_id", "?")
        name   = p.get("name") or "\u0646\u0627\u0634\u0646\u0627\u0633"
        likes  = p.get("likes", [])
        mood   = p.get("mood")
        topics = p.get("topics", [])
        mood_str  = f" | \u062d\u0627\u0644: {mood}" if mood else ""
        like_str  = f" | \u062f\u0648\u0633\u062a \u062f\u0627\u0631\u0647: {', '.join(likes[:2])}" if likes else ""
        topic_str = f" | \u0639\u0644\u0627\u06cc\u0642: {', '.join(topics[:2])}" if topics else ""
        lines.append(f"\u2022 {name} (ID: `{uid}`){like_str}{mood_str}{topic_str}")

    header = f"\u0627\u06cc\u0646\u0627 \u0622\u062f\u0645\u0627\u06cc\u06cc \u0647\u0633\u062a\u0646 \u06a9\u0647 \u062a\u0648 \u062d\u0627\u0641\u0638\u0645\u0646 ({len(profiles)} \u0646\u0641\u0631) \U0001f63e\n\n"
    return header + "\n".join(lines)


def answer_question(user_id: int, text: str) -> str | None:
    mem      = _cache.get(user_id, {})
    name     = mem.get("name")
    likes    = mem.get("likes", [])
    dislikes = mem.get("dislikes", [])
    words    = top_words(mem, 5)
    mood     = mem.get("mood")
    topics   = mem.get("topics", [])
    emojis   = list(mem.get("emoji_freq", {}).keys())
    phrases  = [
        phrase for phrase, count in mem.get("phrase_freq", {}).items()
        if count >= 2
    ]

    if _matches(text, _Q_NAME):
        if name:
            return random.choice([
                f"\u0627\u0633\u0645\u062a {name}\u0647 \U0001f63e \u0641\u06a9\u0631 \u06a9\u0631\u062f\u06cc \u0641\u0631\u0627\u0645\u0648\u0634 \u06a9\u0631\u062f\u0645\u061f",
                f"tch~ {name}. \u0645\u0639\u0644\u0648\u0645\u0647 \u062f\u06cc\u06af\u0647 \U0001f63e",
                f"your name is {name} \u2014 \u06cc\u0627\u062f\u0645\u0647\u060c \u0646\u06af\u0631\u0627\u0646 \u0646\u0628\u0627\u0634 \U0001f63e",
                f"{name}... \u0622\u0631\u0647 \u06cc\u0627\u062f\u0645\u0647 \U0001f63e \u062e\u0648\u0634\u062d\u0627\u0644\u06cc\u061f",
            ])
        return random.choice([
            "\u0627\u0633\u0645\u062a\u0648 \u0628\u0647\u0645 \u0646\u06af\u0641\u062a\u06cc \u06a9\u0647 \U0001f63e \u0628\u06af\u0648 \u062a\u0627 \u06cc\u0627\u062f\u0645 \u0628\u0645\u0648\u0646\u0647",
            "\u0647\u0646\u0648\u0632 \u0627\u0633\u0645\u062a\u0648 \u0646\u062f\u0648\u0646\u0645 \U0001f63e \u0628\u06af\u0648 \u062f\u06cc\u06af\u0647",
            "\u0646\u06af\u0641\u062a\u06cc \u0627\u0633\u0645\u062a \u0686\u06cc\u0647 \u2014 \u0628\u06af\u0648: \u00ab\u0627\u0633\u0645\u0645 ... \u0647\u0633\u062a\u00bb \U0001f63e",
        ])

    if _matches(text, _Q_LIKE):
        if likes:
            listed = "\u060c ".join(likes[:6])
            return random.choice([
                f"\u06cc\u0627\u062f\u0645\u0647 \u06a9\u0647 \u062f\u0648\u0633\u062a \u062f\u0627\u0631\u06cc: {listed} \U0001f63e",
                f"tch~ \u0627\u06cc\u0646\u0627 \u0631\u0648 \u062f\u0648\u0633\u062a \u062f\u0627\u0631\u06cc: {listed}",
                f"\u0639\u0644\u0627\u06cc\u0642\u062a: {listed} \u2014 \u06cc\u0627\u062f\u0645 \u0645\u0648\u0646\u062f\u0647 \U0001f63e",
                f"\u0622\u0631\u0647 \u0622\u0631\u0647\u060c {listed} \u2014 \u0627\u06cc\u0646\u0627 \u0631\u0648 \u062f\u0648\u0633\u062a \u062f\u0627\u0631\u06cc \U0001f63e",
            ])
        return "\u0647\u0646\u0648\u0632 \u0646\u06af\u0641\u062a\u06cc \u0686\u06cc \u062f\u0648\u0633\u062a \u062f\u0627\u0631\u06cc \U0001f63e \u0628\u06af\u0648 \u00ab\u062f\u0648\u0633\u062a \u062f\u0627\u0631\u0645 ...\u00bb"

    if _matches(text, _Q_DISLIKE):
        if dislikes:
            listed = "\u060c ".join(dislikes[:6])
            return random.choice([
                f"\u0627\u0632 \u0627\u06cc\u0646\u0627 \u0628\u062f\u062a \u0645\u06cc\u0627\u062f: {listed} \U0001f63e",
                f"tch~ \u06af\u0641\u062a\u06cc \u0627\u0632 \u0627\u06cc\u0646\u0627 \u0645\u062a\u0646\u0641\u0631\u06cc: {listed}",
                f"\u062f\u06cc\u0633\u0644\u0627\u06cc\u06a9\u0627\u062a: {listed} \u2014 \u0622\u0631\u0647 \u06cc\u0627\u062f\u0645\u0647 \U0001f63e",
                f"\u0627\u06cc\u0646\u0627 \u0631\u0648 \u062f\u0648\u0633\u062a \u0646\u062f\u0627\u0631\u06cc: {listed} \u2014 \u062e\u0648\u062f\u062a \u06af\u0641\u062a\u06cc \U0001f63e",
            ])
        return "\u0646\u06af\u0641\u062a\u06cc \u0627\u0632 \u0686\u06cc \u0628\u062f\u062a \u0645\u06cc\u0627\u062f \U0001f63e \u0628\u06af\u0648 \u00ab\u0627\u0632 ... \u0645\u062a\u0646\u0641\u0631\u0645\u00bb"

    if _matches(text, _Q_MOOD):
        if mood:
            mood_replies = {
                "\u062e\u0648\u0634\u062d\u0627\u0644":    f"\u0622\u0631\u0647 \u062d\u0633\u062a \u062e\u0648\u0628 \u0628\u0648\u062f \u2014 \u06af\u0641\u062a\u06cc {mood} \U0001f63e",
                "\u0646\u0627\u0631\u0627\u062d\u062a":    f"\u06af\u0641\u062a\u06cc \u0646\u0627\u0631\u0627\u062d\u062a\u06cc... \u0627\u0645\u06cc\u062f\u0648\u0627\u0631\u0645 \u0628\u0647\u062a\u0631 \u0634\u062f\u0647 \u0628\u0627\u0634\u06cc \U0001f63e",
                "\u0639\u0635\u0628\u0627\u0646\u06cc":    f"\u06cc\u0627\u062f\u0645\u0647 \u06a9\u0647 \u0639\u0635\u0628\u0627\u0646\u06cc \u0628\u0648\u062f\u06cc \u2014 \u0627\u0644\u0627\u0646 \u0628\u0647\u062a\u0631\u06cc\u061f \U0001f63e",
                "\u0628\u06cc\u200c\u062d\u0648\u0635\u0644\u0647": f"\u06af\u0641\u062a\u06cc \u0628\u06cc\u200c\u062d\u0648\u0635\u0644\u0647\u200c\u0627\u06cc \U0001f63e \u0628\u0631\u0648 \u06cc\u0647 \u06a9\u0627\u0631 \u0645\u0641\u06cc\u062f \u06a9\u0646",
                "\u062e\u0633\u062a\u0647":      f"\u06af\u0641\u062a\u06cc \u062e\u0633\u062a\u0647\u200c\u0627\u06cc \U0001f63e \u0627\u0633\u062a\u0631\u0627\u062d\u062a \u06a9\u0631\u062f\u06cc\u061f",
                "\u0647\u06cc\u062c\u0627\u0646\u200c\u0632\u062f\u0647": f"\u0647\u06cc\u062c\u0627\u0646 \u0632\u062f\u0647 \u0628\u0648\u062f\u06cc \u2014 \u0647\u0646\u0648\u0632\u0645\u061f \U0001f63e",
            }
            return mood_replies.get(mood, f"\u0622\u062e\u0631\u06cc\u0646 \u0628\u0627\u0631 \u06af\u0641\u062a\u06cc \u062d\u0627\u0644\u062a {mood} \u0628\u0648\u062f \U0001f63e")
        return "\u0686\u06cc\u0632 \u062e\u0627\u0635\u06cc \u062f\u0631\u0628\u0627\u0631\u0647 \u062d\u0627\u0644\u062a \u0646\u06af\u0641\u062a\u06cc \u062a\u0627 \u062d\u0627\u0644\u0627 \U0001f63e"

    if _matches(text, _Q_TOPICS):
        if topics:
            listed = "\u060c ".join(topics[:5])
            return f"\u0628\u06cc\u0634\u062a\u0631 \u062f\u0631\u0628\u0627\u0631\u0647 \u0627\u06cc\u0646\u0627 \u062d\u0631\u0641 \u0632\u062f\u06cc: {listed} \U0001f63e"
        return "\u0647\u0646\u0648\u0632 \u0628\u0647 \u0627\u0646\u062f\u0627\u0632\u0647 \u06a9\u0627\u0641\u06cc \u062d\u0631\u0641 \u0646\u0632\u062f\u06cc \u06a9\u0647 \u0628\u0641\u0647\u0645\u0645 \U0001f63e"

    if _matches(text, _Q_ABOUT):
        parts = []
        if name:
            parts.append(f"\u0627\u0633\u0645\u062a: {name}")
        if likes:
            parts.append(f"\u062f\u0648\u0633\u062a \u062f\u0627\u0631\u06cc: {', '.join(likes[:5])}")
        if dislikes:
            parts.append(f"\u0628\u062f\u062a \u0645\u06cc\u0627\u062f \u0627\u0632: {', '.join(dislikes[:5])}")
        if mood:
            parts.append(f"\u0622\u062e\u0631\u06cc\u0646 \u062d\u0627\u0644\u062a: {mood}")
        if topics:
            parts.append(f"\u0645\u0648\u0636\u0648\u0639\u0627\u062a \u0645\u0648\u0631\u062f \u0639\u0644\u0627\u0642\u0647: {', '.join(topics[:4])}")
        if words:
            parts.append(f"\u067e\u0631\u062a\u06a9\u0631\u0627\u0631\u062a\u0631\u06cc\u0646 \u06a9\u0644\u0645\u0627\u062a\u062a: {', '.join(words)}")
        if emojis:
            parts.append(f"\u0627\u06cc\u0645\u0648\u062c\u06cc \u0645\u0648\u0631\u062f \u0639\u0644\u0627\u0642\u0647: {' '.join(emojis[:4])}")
        if phrases:
            parts.append(f"\u062a\u06cc\u06a9\u0647\u200c\u06a9\u0644\u0627\u0645\u0647\u0627\u062a: {', '.join(phrases[:3])}")
        if mem.get("avg_msg_length"):
            parts.append(f"\u0633\u0628\u06a9 \u067e\u06cc\u0627\u0645\u0647\u0627\u062a: {_message_style(mem)}")
        if mem.get("question_count") or mem.get("exclamation_count"):
            parts.append(
                f"\u0633\u0648\u0627\u0644\u200c\u0647\u0627: {mem.get('question_count', 0)} | "
                f"\u062a\u0639\u062c\u0628\u200c\u0647\u0627: {mem.get('exclamation_count', 0)}"
            )
        count = mem.get("msg_count", 0)
        parts.append(f"\u062a\u0639\u062f\u0627\u062f \u067e\u06cc\u0627\u0645\u200c\u0647\u0627\u06cc\u06cc \u06a9\u0647 \u062e\u0648\u0646\u062f\u0645: {count}")
        if parts:
            return "\u0627\u06cc\u0646\u0627 \u0631\u0648 \u0627\u0632\u062a \u06cc\u0627\u062f\u0645\u0647 \U0001f63e\n" + "\n".join(f"\u2022 {p}" for p in parts)
        return "\u0647\u0646\u0648\u0632 \u0686\u06cc\u0632\u06cc \u0627\u0632\u062a \u06cc\u0627\u062f\u0645 \u0646\u06af\u0631\u0641\u062a\u0645 \U0001f63e \u0628\u06cc\u0634\u062a\u0631 \u062d\u0631\u0641 \u0628\u0632\u0646"

    if _matches(text, _Q_WORDS):
        if words:
            return f"\u067e\u0631\u062a\u06a9\u0631\u0627\u0631\u062a\u0631\u06cc\u0646 \u06a9\u0644\u0645\u0627\u062a\u06cc \u06a9\u0647 \u0645\u06cc\u06af\u06cc: {', '.join(words)} \U0001f63e"
        return "\u0647\u0646\u0648\u0632 \u06a9\u0627\u0641\u06cc \u062d\u0631\u0641 \u0646\u0632\u062f\u06cc \u06a9\u0647 \u0628\u0641\u0647\u0645\u0645 \U0001f63e"

    return None


# ── Reply builder ─────────────────────────────────────────────────────────────

_GREET_NAME = {
    "new":     ["\u0627\u0648\u0647\u060c {name} \u0627\u0648\u0645\u062f \U0001f63e", "\u0647\u0627\u061f {name} \u0686\u06cc \u0645\u06cc\u062e\u0648\u0627\u06cc", "tch~ {name}..."],
    "regular": ["{name} \u0628\u0627\u0632 \u0627\u06cc\u0646\u062c\u0627\u06cc\u06cc\u061f", "ohhh {name} \u062f\u0648\u0628\u0627\u0631\u0647 \U0001f63e", "tch~ {name} \u0686\u06cc\u0647\u061f"],
    "friend":  ["\u062f\u0648\u0628\u0627\u0631\u0647 \u062a\u0648 \U0001f63e {name}\u060c \u0686\u06cc\u0647 \u0628\u0627\u0632\u061f", "\u0622\u0647 {name}... \u062f\u0648\u0628\u0627\u0631\u0647\u061f \U0001f63e", "{name} \u06a9\u0647 \u0645\u06cc\u06af\u0645 \u062f\u0633\u062a \u0628\u0631\u062f\u0627\u0631 \U0001f63e"],
}
_GREET_ANON = ["\u0647\u0627\u061f \u0686\u06cc \u0645\u06cc\u062e\u0648\u0627\u06cc \U0001f63e", "tch~ \u0686\u06cc\u0647 \u0628\u0627\u0632", "\u0628\u06af\u0648 \u0686\u06cc \u0645\u06cc\u062e\u0648\u0627\u06cc", "\u0627\u0648\u0645\u062f\u06cc \u0686\u06cc\u06a9\u0627\u0631 \U0001f63e"]

_MOOD_REPLIES: dict[str, list[str]] = {
    "\u062e\u0648\u0634\u062d\u0627\u0644":    ["\u062e\u0648\u0634\u062d\u0627\u0644\u06cc\u061f \u062a\u0639\u062c\u0628 \u0646\u0645\u06cc\u06a9\u0646\u0645 \U0001f63e", "\u0627\u06cc \u0628\u0627\u0628\u0627 \u062e\u0648\u0634\u062d\u0627\u0644\u06cc \u2014 \u0645\u0646\u0645 \u062e\u0648\u0634\u062d\u0627\u0644\u0645 \u06a9\u0647 \u062e\u0648\u0634\u062d\u0627\u0644\u06cc \U0001f63e"],
    "\u0646\u0627\u0631\u0627\u062d\u062a":    ["\u0646\u0627\u0631\u0627\u062d\u062a\u06cc\u061f tch~ \u0628\u06af\u0648 \u0686\u062a\u0647 \U0001f63e", "\u0627\u06af\u0647 \u0646\u0627\u0631\u0627\u062d\u062a\u06cc... \u0628\u06af\u0648 \u062f\u06cc\u06af\u0647 \U0001f63e"],
    "\u0639\u0635\u0628\u0627\u0646\u06cc":    ["\u0639\u0635\u0628\u0627\u0646\u06cc\u061f \u0622\u0631\u0648\u0645 \u0628\u0627\u0634 \U0001f63e", "tch~ \u0627\u0648\u0646 \u0642\u062f\u0631\u0627 \u0647\u0645 \u0628\u062f \u0646\u06cc\u0633\u062a \u0627\u0644\u0627\u0646 \U0001f63e"],
    "\u0628\u06cc\u200c\u062d\u0648\u0635\u0644\u0647": ["\u0628\u06cc\u200c\u062d\u0648\u0635\u0644\u0647\u200c\u0627\u06cc\u061f \u0645\u0646\u0645 \U0001f63e", "tch~ \u062d\u0648\u0635\u0644\u0647 \u062f\u0627\u0631\u06cc \u0627\u06cc\u0646 \u067e\u06cc\u0627\u0645 \u0631\u0648 \u0628\u0641\u0631\u0633\u062a\u06cc \u0627\u0645\u0627 \u06a9\u0627\u0631 \u0645\u0641\u06cc\u062f \u0646\u0647\u061f \U0001f63e"],
    "\u062e\u0633\u062a\u0647":      ["\u062e\u0633\u062a\u0647\u200c\u0627\u06cc\u061f \u06cc\u0647 \u06a9\u0645 \u0627\u0633\u062a\u0631\u0627\u062d\u062a \u06a9\u0646 \U0001f63e", "\u0647\u0645\u0647 \u062e\u0633\u062a\u0647\u200c\u0627\u0646 \u062a\u0648 \u06a9\u0647 \u0645\u062e\u0635\u0648\u0635 \u0646\u06cc\u0633\u062a\u06cc \U0001f63e"],
    "\u0647\u06cc\u062c\u0627\u0646\u200c\u0632\u062f\u0647": ["\u0647\u06cc\u062c\u0627\u0646 \u0632\u062f\u06cc\u061f \u0622\u0631\u0648\u0645 \u0628\u0627\u0634 \U0001f63e", "\u0627\u06cc\u0646\u0642\u062f\u0631 \u0647\u06cc\u062c\u0627\u0646 \u0646\u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634 \U0001f63e"],
}

_LIKE_REPLY = [
    "\u0627\u0648\u0647 \u067e\u0633 {item} \u062f\u0648\u0633\u062a \u062f\u0627\u0631\u06cc... \u062c\u0627\u0644\u0628\u0647 \U0001f63e",
    "tch~ {item}\u061f \u0627\u0646\u062a\u0638\u0627\u0631 \u0628\u0647\u062a\u0631\u06cc \u0646\u062f\u0627\u0634\u062a\u0645",
    "\u062e\u0628 \u0628\u06cc\u062e\u0648\u062f \u062f\u0648\u0633\u062a \u062f\u0627\u0631\u06cc {item} \u0631\u0648 \U0001f63e",
    "{item}\u061f \u0622\u0631\u0647 \u0628\u062f \u0646\u06cc\u0633\u062a \U0001f63e",
]
_DISLIKE_REPLY = [
    "\u0627\u0632 {item} \u0628\u062f\u062a \u0645\u06cc\u0627\u062f\u061f \u0639\u0627\u0642\u0628\u062a \u06cc\u0647 \u0686\u06cc\u0632 \u062f\u0631\u0633\u062a\u06cc \u06af\u0641\u062a\u06cc \U0001f63e",
    "tch~ {item}\u061f \u0645\u0646\u0645 \u0647\u0645\u06cc\u0646\u0637\u0648\u0631 \U0001f63e",
    "\u0622\u0631\u0647 {item} \u0648\u0627\u0642\u0639\u0627\u064b \u0645\u0632\u062e\u0631\u0641\u0647 \U0001f63e",
]
_TOPIC_REPLY = [
    "\u0628\u0627\u0632 \u0631\u0627\u062c\u0639 \u0628\u0647 {topic} \u062d\u0631\u0641 \u0645\u06cc\u0632\u0646\u06cc \U0001f63e",
    "tch~ {topic} \u062f\u06cc\u06af\u0647... \U0001f63e",
    "\u0647\u0645\u06cc\u0634\u0647 {topic} {topic} \u0645\u06cc\u06a9\u0646\u06cc \U0001f63e",
]
_WORD_REPLY = [
    "\u0647\u0646\u0648\u0632\u0645 \u00ab{word}\u00bb \u0645\u06cc\u06af\u06cc\u061f \U0001f63e",
    'tch~ "{word}" \u062f\u06cc\u06af\u0647 \u0686\u06cc \U0001f63e',
]
_GENERIC = [
    "\u0686\u06cc\u0647 \u0628\u0627\u0632 \U0001f63e", "tch~ \U0001f63e", "\u0647\u0648\u0648\u0648\u0641 \U0001f63e",
    "\u062e\u0628\u061f \U0001f63e", "\u0627\u062f\u0627\u0645\u0647 \u0628\u062f\u0647 \U0001f63e", "\u0628\u0644\u0647\u061f \U0001f63e",
    "hmm \U0001f63e", "\u0628\u06af\u0648 \U0001f63e",
]
_BIRTHDAY_REPLY = [
    "\u062a\u0648\u0644\u062f\u062a \u0645\u0628\u0627\u0631\u06a9 \U0001f63e \u062e\u0648\u0634\u062d\u0627\u0644\u0645 \u06a9\u0647 \u06af\u0641\u062a\u06cc",
    "\u062a\u0648\u0644\u062f\u062a \u0645\u0628\u0627\u0631\u06a9\u0647... tch~ \u062e\u0648\u0634 \u0628\u0627\u0634\u06cc \U0001f63e",
    "\u0627\u0648\u0647 \u062a\u0648\u0644\u062f\u062a\u0647\u061f \U0001f63e \u062e\u0648\u0634\u062d\u0627\u0644 \u0628\u0627\u0634\u06cc",
]


def _personalized_reply_options(mem: dict, their_text: str = "") -> list[str]:
    """Build reply options from facts and habits learned for this user."""
    name = mem.get("name") or "\u062f\u0648\u0633\u062a \u0645\u0646"
    likes = mem.get("likes", [])
    dislikes = mem.get("dislikes", [])
    topics = mem.get("topics", [])
    words = top_words(mem, 5)
    emojis = list(mem.get("emoji_freq", {}).keys())
    phrases = [
        phrase for phrase, count in mem.get("phrase_freq", {}).items()
        if count >= 2
    ]
    style = _message_style(mem)
    options = []

    if likes:
        options.extend([
            f"{name}\u060c \u0628\u0627\u0632 \u062f\u0627\u0631\u06cc \u0633\u0631\u0627\u063a {random.choice(likes)} \u0645\u06cc\u0631\u06cc\u061f \u06cc\u0627\u062f\u0645\u0647 \u062f\u0648\u0633\u062a\u0634 \u062f\u0627\u0631\u06cc \U0001f63e",
            f"{name}\u060c \u0627\u06cc\u0646\u0645 \u0645\u0648\u0636\u0648\u0639 \u0628\u0647\u062a \u0645\u06cc\u0627\u062f\u061b \u062a\u0648 \u06a9\u0647 \u0628\u0627\u0632\u0645 \u0633\u0631\u0627\u063a\u0634 \u0631\u0641\u062a\u06cc \U0001f63e",
        ])
    if dislikes:
        options.append(
            f"{name}\u060c \u0645\u06cc\u062f\u0648\u0646\u0645 \u0627\u0632 {random.choice(dislikes)} \u062e\u0648\u0634\u062a \u0646\u0645\u06cc\u0627\u062f\u060c \u0648\u0644\u06cc \u0628\u0627\u0632 \u062d\u0631\u0641\u0634 \u0634\u062f \U0001f63e"
        )
    if topics:
        options.append(
            f"{name}\u060c \u0628\u0627\u0632 \u0631\u0627\u062c\u0639 \u0628\u0647 {random.choice(topics)} \u062d\u0631\u0641 \u0645\u06cc\u0632\u0646\u06cc\u061b \u0627\u06cc\u0646 \u062f\u06cc\u06af\u0647 \u0639\u0627\u062f\u062a\u062a \u0634\u062f\u0647 \U0001f63e"
        )
    if mem.get("mood"):
        options.append(
            f"{name}\u060c \u06cc\u0627\u062f\u0645\u0647 \u0622\u062e\u0631\u06cc\u0646 \u0628\u0627\u0631 \u062d\u0627\u0644\u062a {mem['mood']} \u0628\u0648\u062f\u061b \u0627\u0644\u0627\u0646 \u0647\u0645\u0648\u0646\u06cc\u061f \U0001f63e"
        )
    if phrases:
        options.append(
            f"{name}\u060c \u00ab{random.choice(phrases)}\u00bb \u0647\u0645 \u0628\u0627\u0632 \u0627\u0648\u0645\u062f\u061b \u0627\u06cc\u0646 \u062f\u06cc\u06af\u0647 \u062a\u06cc\u06a9\u0647\u200c\u06a9\u0644\u0627\u0645\u062a\u0647 \U0001f63e"
        )
    if emojis:
        options.append(
            f"{name}\u060c \u0627\u06cc\u0646 {emojis[0]} \u062f\u06cc\u06af\u0647 \u0627\u0645\u0636\u0627\u06cc \u067e\u06cc\u0627\u0645\u200c\u0647\u0627\u062a\u0647 \U0001f63e"
        )
    if style == "short":
        options.append(f"{name}\u060c \u0645\u062b\u0644 \u0647\u0645\u06cc\u0634\u0647 \u06a9\u0648\u062a\u0627\u0647 \u0648 \u0645\u0641\u06cc\u062f \u06af\u0641\u062a\u06cc \U0001f63e")
    elif style == "long":
        options.append(f"{name}\u060c \u0628\u0627\u0632 \u06cc\u0647 \u067e\u06cc\u0627\u0645 \u0645\u0641\u0635\u0644 \u0641\u0631\u0633\u062a\u0627\u062f\u06cc\u061b \u0639\u0627\u062f\u062a\u062a\u0647 \u062f\u06cc\u06af\u0647 \U0001f63e")
    if their_text and words:
        for word in words:
            if word in their_text.lower():
                options.append(random.choice(_WORD_REPLY).format(word=word))
                break
    return options


def build_reply(user_id: int, their_text: str = "") -> str:
    mem      = _cache.get(user_id, {})
    name     = mem.get("name")
    likes    = mem.get("likes", [])
    dislikes = mem.get("dislikes", [])
    mood     = mem.get("mood")
    topics   = mem.get("topics", [])
    fam      = _familiarity(mem)
    personalized = _personalized_reply_options(mem, their_text)

    # Birthday first
    if _detect_birthday(their_text):
        return random.choice(_BIRTHDAY_REPLY)

    # Give learned facts and habits their own random chance before generic
    # replies, so the bot does not merely mention memory incidentally.
    if personalized and random.random() < 0.55:
        return random.choice(personalized)

    pool = []

    # Mood-aware
    if mood and random.random() < 0.3:
        pool += _MOOD_REPLIES.get(mood, [])

    # Familiarity greeting
    if name:
        pool += [t.format(name=name) for t in _GREET_NAME.get(fam, _GREET_NAME["new"])]
    else:
        pool += _GREET_ANON[:]

    if likes and random.random() < 0.35:
        pool.append(random.choice(_LIKE_REPLY).format(item=random.choice(likes)))

    if dislikes and random.random() < 0.35:
        pool.append(random.choice(_DISLIKE_REPLY).format(item=random.choice(dislikes)))

    if topics and random.random() < 0.25:
        pool.append(random.choice(_TOPIC_REPLY).format(topic=random.choice(topics)))

    pool += personalized
    pool += _GENERIC
    return random.choice(pool)


# ── Tag builder ───────────────────────────────────────────────────────────────

_TAG_NAME = [
    "oi {name}! {mention} \u06a9\u062c\u0627\u06cc\u06cc\u061f \U0001f63e",
    "{name}! {mention} \u0628\u06cc\u0627 \u0627\u06cc\u0646\u062c\u0627 \U0001f43e",
    "tch~ {name} {mention} \u063a\u06cc\u0628\u062a \u0632\u062f\u0647\u061f \U0001f63e",
    "{mention} ({name}) \u0634\u0646\u06cc\u062f\u06cc \u06cc\u0627 \u0646\u0647\u061f \U0001f63e",
]
_TAG_LIKE = [
    "{mention} \u0628\u0631\u0648 {item} \u0628\u062e\u0631 \u062e\u0648\u062f\u062a\u0648 \u0645\u0634\u063a\u0648\u0644 \u06a9\u0646 \U0001f63e",
    "\u0647\u06cc {mention} \u0641\u06a9\u0631 \u06a9\u0631\u062f\u0645 \u0628\u0631\u06cc \u062f\u0646\u0628\u0627\u0644 {item} \u06af\u0645 \u0634\u062f\u06cc \U0001f63e",
]
_TAG_MOOD: dict[str, str] = {
    "\u0646\u0627\u0631\u0627\u062d\u062a":    "{mention} \u062d\u0627\u0644\u062a \u062e\u0648\u0628\u0647\u061f \U0001f63e",
    "\u062e\u0633\u062a\u0647":      "{mention} \u0628\u0627\u0632\u0645 \u062e\u0633\u062a\u0647\u200c\u0627\u06cc\u061f \U0001f63e",
    "\u0628\u06cc\u200c\u062d\u0648\u0635\u0644\u0647": "{mention} \u0628\u06cc\u200c\u062d\u0648\u0635\u0644\u0647 \u0646\u0634\u06cc\u0646 \U0001f63e",
    "\u0647\u06cc\u062c\u0627\u0646\u200c\u0632\u062f\u0647": "{mention} \u0647\u06cc\u062c\u0627\u0646 \u062f\u0627\u0631\u06cc \u0647\u0646\u0648\u0632\u0645\u061f \U0001f63e",
}
_TAG_TOPIC: dict[str, str] = {
    "\u06af\u06cc\u0645\u06cc\u0646\u06af":   "{mention} \u0628\u0631\u0648 \u06af\u06cc\u0645 \u0628\u0627\u0632\u06cc \u06a9\u0646 \u0628\u062c\u0627\u06cc \u063a\u06cc\u0628 \u0632\u062f\u0646 \U0001f63e",
    "\u0641\u06cc\u0644\u0645":     "{mention} \u06af\u0648\u0634\u06cc \u062f\u0627\u0631\u06cc \u0633\u0631\u06cc\u0627\u0644 \u0646\u06af\u0627\u0647 \u0645\u06cc\u06a9\u0646\u06cc\u061f \U0001f63e",
    "\u0645\u0648\u0633\u06cc\u0642\u06cc":  "{mention} \u0628\u0631\u0648 \u0622\u0647\u0646\u06af \u06af\u0648\u0634 \u0628\u062f\u0647 \u0628\u062c\u0627\u06cc \u063a\u06cc\u0628 \u0634\u062f\u0646 \U0001f63e",
}
_TAG_GENERIC = [
    "oi {mention} \u06a9\u062c\u0627 \u0631\u0641\u062a\u06cc\u061f \U0001f63e",
    "{mention} \u0634\u0646\u06cc\u062f\u06cc \u06cc\u0627 \u0646\u0647\u061f \U0001f43e",
    "tch~ {mention} \u0628\u06cc\u0627 \u0627\u06cc\u0646\u062c\u0627 \U0001f63e",
    "{mention} \u0645\u0631\u062f\u06cc\u061f \U0001f63e",
    "\u0647\u06cc {mention}! \U0001f43e",
]


def build_tag(user_id: int, mention: str) -> str:
    mem    = _cache.get(user_id, {})
    name   = mem.get("name")
    likes  = mem.get("likes", [])
    mood   = mem.get("mood")
    topics = mem.get("topics", [])

    pool = []

    # Mood tag
    if mood and mood in _TAG_MOOD:
        pool.append(_TAG_MOOD[mood].format(mention=mention))

    # Topic tag
    if topics:
        for t in topics:
            if t in _TAG_TOPIC:
                pool.append(_TAG_TOPIC[t].format(mention=mention))
                break

    if name:
        pool += [t.format(name=name, mention=mention) for t in _TAG_NAME]

    if likes:
        item = random.choice(likes)
        pool += [t.format(mention=mention, item=item) for t in _TAG_LIKE]

    pool += [t.format(mention=mention) for t in _TAG_GENERIC]
    return random.choice(pool)
