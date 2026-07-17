import random
from pyrogram import filters, enums
from pyrogram.client import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from Adarsh.bot import StreamBot
from Adarsh.utils.database import Database
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

@StreamBot.on_message(filters.group & ~filters.service)
async def group_tagger_handler(c: Client, m: Message):
    if not m.from_user or m.from_user.is_bot:
        return

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
            '🤩',
            '🤩',
            
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
        username_val = random_user.get('username')
        
        # Format the mention properly
        if username_val and not username_val.replace('_', '').isalnum(): # Check if it's a real username
             mention = f"@{username_val}"
        elif username_val:
             mention = f"@{username_val}"
        else:
             mention = f"[{random_user.get('first_name', 'User')}](tg://user?id={user_id})"
        
        messages = [
            f"Meow~ {mention} you haven't added arts today 💘💮",
            f"nyaaa~ stop ignoring me {mention} senpai~ 🐾",
            f"I miss you {mention} ~ 🐾"
        ]
        
        await m.reply_text(random.choice(messages))

@StreamBot.on_message(filters.command('ping'))
async def ping_handler(bot, m: Message):
    start = time.time()
    reply = await m.reply_text("🏓 Pong!")
    elapsed = (time.time() - start) * 1000
    await reply.edit_text(f"🏓 Pong!\n<b>Speed:</b> <code>{elapsed:.2f} ms</code>", parse_mode=enums.ParseMode.HTML)

@StreamBot.on_message(filters.command('stats') & filters.private)
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
