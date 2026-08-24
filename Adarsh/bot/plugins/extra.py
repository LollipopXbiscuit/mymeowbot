import re
import random
from pyrogram import filters, enums
from pyrogram.client import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from Adarsh.bot import StreamBot
from Adarsh.utils.database import Database
from Adarsh.utils.ai_memory import observe, build_reply, build_tag, answer_question, is_friends_question, list_friends
from Adarsh.vars import Var
import time
import shutil, psutil
from Adarsh import StartTime

# Note: We need to define human_readable functions since utils_bot might not be available
def readable_time(seconds: int) -> str:
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        if count < 3:
            remainder, result = divmod(seconds, 60)
        else:
            remainder, result = divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    for i in range(len(time_list)):
        time_list[i] = str(time_list[i]) + time_suffix_list[i]
    if len(time_list) == 4:
        ping_time += time_list.pop() + ", "
    time_list.reverse()
    ping_time += ":".join(time_list)
    return ping_time

def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return '0B'
    step_unit = 1024.0
    for x in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < step_unit:
            return "%3.1f %s" % (size_in_bytes, x)
        size_in_bytes /= step_unit
    return "%3.1f %s" % (size_in_bytes, 'TB')

db = Database(Var.DATABASE_URL, Var.name)
message_counters = {}

# In-memory message store per group: {chat_id: [text, ...]} — fallback when DB is unavailable
_group_msg_cache: dict = {}
_MAX_CACHE = 300  # max messages kept per group in memory


def _cache_message(chat_id: int, text: str):
    """Store a message text in the in-memory cache (bounded)."""
    bucket = _group_msg_cache.setdefault(chat_id, [])
    bucket.append(text)
    if len(bucket) > _MAX_CACHE:
        bucket.pop(0)


def _random_cached_message(chat_id: int):
    bucket = _group_msg_cache.get(chat_id, [])
    return random.choice(bucket) if bucket else None


@StreamBot.on_message(filters.group & ~filters.service)
async def group_tagger_handler(c: Client, m: Message):
    if not m.from_user or m.from_user.is_bot:
        return

    # "بگو X" — delete user's message and repeat X
    if m.text and m.text.strip().startswith("بگو "):
        text_to_say = m.text.strip()[len("بگو "):].strip()
        if text_to_say:
            try:
                await m.delete()
            except Exception:
                pass
            await c.send_message(m.chat.id, text_to_say)
            return

    # Store non-command text and update user memory profile
    if m.text and not m.text.startswith('/') and len(m.text.strip()) > 1:
        _cache_message(m.chat.id, m.text)
        try:
            await observe(m.from_user.id, m.text)   # updates name/likes/dislikes/words
        except Exception:
            pass
        try:
            await db.add_group_message(m.chat.id, m.text)
        except Exception:
            pass

    # Track users in the group
    try:
        await db.add_group_user(m.chat.id, m.from_user.id, m.from_user.username or m.from_user.first_name)
    except Exception:
        pass  # DB unavailable — skip tracking, don't crash the dispatcher

    # Initialize counter for the group
    if m.chat.id not in message_counters:
        message_counters[m.chat.id] = {
            'count': 0,
            'target': random.randint(50, 100)
        }

    message_counters[m.chat.id]['count'] += 1

    # Added: Specific reminder message every 10 messages
    if message_counters[m.chat.id]['count'] % 10 == 0:
        reminder_messages = [
            "آرت نزدید کونگشادا",
            "@siln3c سلم خبی",
            " عمه ات را خریدارم @Gilgamesh_shah",
            "(ﾉ^ω^)ﾉﾟ عسل بانو خسته نباشی عزیزم",
            "@im_nefer نفس من کیه؟ OWO",
            "@IM_NEMIDOONAM مامی فدات شه",
            "@xnaixx بخورمتتتتتتتتتتتتتت زن OWO",
            "(ﾉ^ω^)ﾉﾟ الو؟ سلام؟ شما خیلی سکسی هستید @nicol_ll5",
            'بهم توجه کنید 🌟',
            "(╯°□°）╯︵ (﻿ .o.)انگول کنید منو دیگه چند ساعته هیچی اپلود نکردم اههههههههههههههههههههههههههه",
            "کسی کمک نمیخواد؟ -w-",
            "@Aysariy چرا انقدر بهم بی محلی میکنی (T_T)",
            "میشه لطفا از منم ارت بزنیدددددددددددددددددد یه پیشی گوکولی لطفاااااااااااااااااااااا",
            "-_- خواهرم بهم بی محلی میکنه @waifuscollectorbot",
            '😽',
            '😾',
            
        ]
        await m.reply_text(random.choice(reminder_messages), parse_mode=enums.ParseMode.HTML)

    # Check if we reached the random target
    if message_counters[m.chat.id]['count'] >= message_counters[m.chat.id]['target']:
        # Reset counter
        message_counters[m.chat.id]['count'] = 0
        message_counters[m.chat.id]['target'] = random.randint(50, 100)

        # Get random user to tag
        random_user = await db.get_random_group_user(m.chat.id)
        if not random_user:
            return

        user_id = random_user['id']
        display = random_user.get('username') or random_user.get('first_name') or 'User'
        mention = f"[{display}](tg://user?id={user_id})"
        
        tag_msg = build_tag(user_id, mention)
        await m.reply_text(tag_msg)

@StreamBot.on_message((filters.group | filters.private) & filters.text & filters.create(lambda _, __, m: bool(m.text and m.text.strip() == "\u0645\u06cc\u0648")))
async def miyo_handler(c: Client, m: Message):
    await m.reply_text("\u0628\u0627 \u0645\u0646\u06cc\u061f \U0001f63e")



@StreamBot.on_message(filters.group & filters.reply, group=1)
async def echo_bot_reply_handler(c: Client, m: Message):
    """When a group member replies to a bot message, repeat a past member message
    verbatim (70 % of the time) or fall back to a memory-based reply."""
    replied = m.reply_to_message
    if not replied or not replied.from_user:
        return
    bot_id = c.me.id if c.me else None
    if bot_id is None or replied.from_user.id != bot_id:
        return
    if m.from_user and m.from_user.is_bot:
        return

    user_text = (m.text or m.caption or "").strip()

    # Friends list question (needs DB — async)
    if is_friends_question(user_text):
        await m.reply_text(await list_friends())
        return

    # Other memory questions (sync, from cache)
    memory_answer = answer_question(m.from_user.id, user_text)
    if memory_answer:
        await m.reply_text(memory_answer)
        return

    # 70 % chance: copy-paste a random past member message verbatim
    pool = _group_msg_cache.get(m.chat.id, [])
    if pool and random.random() < 0.70:
        candidates = [msg for msg in pool if msg.strip() != user_text]
        chosen = random.choice(candidates) if candidates else random.choice(pool)
        await m.reply_text(chosen)
    else:
        await m.reply_text(build_reply(m.from_user.id, user_text))


@StreamBot.on_message(filters.private & filters.text & ~filters.command([
    "start", "help", "about", "stats", "users", "broadcast", "login",
    "allow", "disallow", "allowedgroups"
]), group=2)
async def private_memory_handler(c: Client, m: Message):
    """Answer memory questions and respond to any text in private chat."""
    if not m.from_user or m.from_user.is_bot:
        return
    text = m.text or ""

    # "بگو X" — delete user's message and repeat X
    if text.strip().startswith("بگو "):
        text_to_say = text.strip()[len("بگو "):].strip()
        if text_to_say:
            try:
                await m.delete()
            except Exception:
                pass
            await c.send_message(m.chat.id, text_to_say)
            return

    # Feed message into memory
    try:
        await observe(m.from_user.id, text)
    except Exception:
        pass
    # Friends list question (needs DB — async)
    if is_friends_question(text):
        await m.reply_text(await list_friends())
        return

    # Other memory questions (sync, from cache)
    answer = answer_question(m.from_user.id, text)
    if answer:
        await m.reply_text(answer)
    else:
        await m.reply_text(build_reply(m.from_user.id, text))


@StreamBot.on_message(filters.regex(r'^/ping(@\w+)?(\s|$)'), group=1)
async def ping_handler(bot, m: Message):
    start = time.time()
    reply = await m.reply_text("what the hell do you want 😾")
    elapsed = (time.time() - start) * 1000
    await reply.edit_text(f"yeah I'm alive, <b>{elapsed:.0f}ms</b>. stop checking on me like I'd ever just disappear on you 😾", parse_mode=enums.ParseMode.HTML)

@StreamBot.on_message(filters.command('stats') & filters.private, group=1)
async def stats(bot, update):
  currentTime = readable_time(int(time.time() - StartTime))
  total, used, free = shutil.disk_usage('.')
  total = get_readable_file_size(total)
  used = get_readable_file_size(used)
  free = get_readable_file_size(free)
  sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
  recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
  cpuUsage = psutil.cpu_percent(interval=0.5)
  memory = psutil.virtual_memory().percent
  disk = psutil.disk_usage('/').percent
  botstats = f'<b>Bot Uptime:</b> {currentTime}\n' \
            f'<b>Total disk space:</b> {total}\n' \
            f'<b>Used:</b> {used}  ' \
            f'<b>Free:</b> {free}\n\n' \
            f'📊Data Usage📊\n<b>Upload:</b> {sent}\n' \
            f'<b>Down:</b> {recv}\n\n' \
            f'<b>CPU:</b> {cpuUsage}% ' \
            f'<b>RAM:</b> {memory}% ' \
            f'<b>Disk:</b> {disk}%'
  await update.reply_text(botstats)
