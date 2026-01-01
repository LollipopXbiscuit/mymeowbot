#Aadhi000 
from Adarsh.bot import StreamBot
from Adarsh.vars import Var
import logging
logger = logging.getLogger(__name__)
from Adarsh.bot.plugins.stream import MY_PASS
from Adarsh.utils.human_readable import humanbytes
from Adarsh.utils.database import Database
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from Adarsh.utils.file_properties import get_name, get_hash, get_media_file_size
db = Database(Var.DATABASE_URL, Var.name)
from pyrogram.types import ReplyKeyboardMarkup

                      
@StreamBot.on_message(filters.command('start') & filters.private)
async def start(b, m):
    if not await db.is_user_exist(m.from_user.id):
        await db.add_user(m.from_user.id)
        await b.send_message(
            Var.BIN_CHANNEL,
            f"#NEW_USER: \n\nNew User [{m.from_user.first_name}](tg://user?id={m.from_user.id}) Started !!"
        )
    usr_cmd = m.text.split("_")[-1]
    if usr_cmd == "/start":
        if Var.UPDATES_CHANNEL and Var.UPDATES_CHANNEL != "None":
            try:
                user = await b.get_chat_member(Var.UPDATES_CHANNEL, m.chat.id)
                if user.status == "banned":
                    await b.send_message(
                        chat_id=m.chat.id,
                        text="Nyaa~! Master, you are banned from using me! 😿",
                        disable_web_page_preview=True
                    )
                    return
            except UserNotParticipant:
                await b.send_message(
                    chat_id=m.chat.id,
                    text="**Nyaa~! Master, please join my updates channel to use me! 🐾✨**\n\n**Only channel subscribers can use my magic! Nyaa~!**",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton("Join Now 🐾", url=f"https://t.me/{Var.UPDATES_CHANNEL}")
                            ]
                        ]
                    )
                    
                )
                return
            except Exception as e:
                logger.error(f"Error in force sub: {e}")
                # If error, proceed without force sub to avoid breaking start
        
        await m.reply_photo(
            photo="https://telegra.ph/file/3cd15a67ad7234c2945e7.jpg",
            caption="**Nyaa~! Hello there, master! 🐾✨\n\nI'm your cute little File Streamer! I can turn your videos and images into permanent links! Nyaa~ 💖**\n\n**Use /help for more details\n\nSend me any video or file, or reply to one with /convert in a group to see my magic! Nyaa~! ✨**",
        )
    else:
        if Var.UPDATES_CHANNEL and Var.UPDATES_CHANNEL != "None":
            try:
                user = await b.get_chat_member(Var.UPDATES_CHANNEL, m.chat.id)
                if user.status == "banned":
                    await b.send_message(
                        chat_id=m.chat.id,
                        text="Nyaa~! Master, you are banned! 😿",
                        disable_web_page_preview=True
                    )
                    return
            except UserNotParticipant:
                await b.send_message(
                    chat_id=m.chat.id,
                    text="**Nyaa~! Master, please join my updates channel! 🐾✨**",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton("Join Now 🐾", url=f"https://t.me/{Var.UPDATES_CHANNEL}")
                            ]                           
                        ]
                    )
                    
                )
                return
            except Exception as e:
                logger.error(f"Error in force sub: {e}")

        get_msg = await b.get_messages(chat_id=Var.BIN_CHANNEL, ids=int(usr_cmd))

        file_size = None
        if get_msg.video:
            file_size = f"{humanbytes(get_msg.video.file_size)}"
        elif get_msg.document:
            file_size = f"{humanbytes(get_msg.document.file_size)}"
        elif get_msg.audio:
            file_size = f"{humanbytes(get_msg.audio.file_size)}"

        file_name = None
        if get_msg.video:
            file_name = f"{get_msg.video.file_name}"
        elif get_msg.document:
            file_name = f"{get_msg.document.file_name}"
        elif get_msg.audio:
            file_name = f"{get_msg.audio.file_name}"

        stream_link = "https://{}/{}".format(Var.FQDN, get_msg.id) if Var.ON_HEROKU or Var.NO_PORT else \
            "http://{}:{}/{}".format(Var.FQDN,
                                     Var.PORT,
                                     get_msg.id)

        msg_text = "**Nyaa~! Your link is ready, master! 🐾✨\n\n📧 ғɪʟᴇ ɴᴀᴍᴇ :-\n{}\n {}\n\n💌 ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋ :- {}\n\n♻️ This link is permanent! Nyaa~! ♻️**"
        await m.reply_text(            
            text=msg_text.format(file_name, file_size, stream_link),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Download Now 🐾 ⚡", url=stream_link)]])
        )


@StreamBot.on_message(filters.command('help') & filters.private)
async def help_handler(bot, message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id)
        await bot.send_message(
            Var.BIN_CHANNEL,
            f"#NEW_USER: \n\nNew User [{message.from_user.first_name}](tg://user?id={message.from_user.id}) Started !!"
        )
    await message.reply_photo(
            photo="https://telegra.ph/file/3cd15a67ad7234c2945e7.jpg",
            caption="**Nyaa~! Here's how to use me, master! 🐾✨\n\n┣⪼ Send me any file or video in private and I'll give you a permanent link! Nyaa~!\n\n┣⪼ In groups, reply to a file with /convert and I'll generate the link for you! ✨\n\n┣⪼ You can use the link to download or stream on external players! 🐾\n\n┣⪼ I also support channels! Add me as admin to get links automatically! Nyaa~! ✨\n\nFor more info use /about! 💖**", 
    )

@StreamBot.on_message(filters.command('about') & filters.private)
async def about_handler(bot, message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id)
        await bot.send_message(
            Var.BIN_CHANNEL,
            f"#NEW_USER: \n\nNew User [{message.from_user.first_name}](tg://user?id={message.from_user.id}) Started !!"
        )
    await message.reply_photo(
            photo="https://telegra.ph/file/3cd15a67ad7234c2945e7.jpg",
            caption="""<b>Nyaa~! Some hidden details about me! 🐾😜</b>

<b>╭━━━━━━━〔 Cute Stream Bot 〕</b>
┃
┣⪼<b>Bot Name : File To Link</b>
┣⪼<b>Updates : MW Updatez</b>
┣⪼<b>Support : Opus Techz</b>
┣⪼<b>Library : Pyrogram</b>
┣⪼<b>Language: Python 3</b>
┃
<b>╰━━━━━━━〔 Please Support Nyaa~! 〕</b>""",
    )
