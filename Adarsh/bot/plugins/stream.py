#(c) Adarsh-Goel
import os
import asyncio
from asyncio import TimeoutError
from Adarsh.bot import StreamBot
from Adarsh.utils.database import Database
from Adarsh.utils.human_readable import humanbytes
from Adarsh.vars import Var
from urllib.parse import quote_plus
from pyrogram import filters, Client
from pyrogram.errors import FloodWait, UserNotParticipant
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from Adarsh.utils.file_properties import get_name, get_hash, get_media_file_size
db = Database(Var.DATABASE_URL, Var.name)


MY_PASS = os.environ.get("MY_PASS",None)
pass_dict = {}
pass_db = Database(Var.DATABASE_URL, "ag_passwords")


@StreamBot.on_message((filters.regex("login🔑") | filters.command("login")) , group=4)
async def login_handler(c: Client, m: Message):
    try:
        try:
            ag = await m.reply_text("Now send me password.\n\n If You don't know check the MY_PASS Variable in heroku \n\n(You can use /cancel command to cancel the process)")
            _text = await c.listen(m.chat.id, filters=filters.text, timeout=90)
            if _text.text:
                textp = _text.text
                if textp=="/cancel":
                   await ag.edit("Process Cancelled Successfully")
                   return
            else:
                return
        except TimeoutError:
            await ag.edit("I can't wait more for password, try again")
            return
        if textp == MY_PASS:
            await pass_db.add_user_pass(m.chat.id, textp)
            ag_text = "yeah! you entered the password correctly"
        else:
            ag_text = "Wrong password, try again"
        await ag.edit(ag_text)
    except Exception as e:
        print(e)

@StreamBot.on_message((filters.private | filters.group) & (filters.document | filters.video | filters.audio | filters.photo | filters.voice) , group=4)
async def private_receive_handler(c: Client, m: Message):
    # Handle /convert command in groups
    if m.chat.type in ["group", "supergroup"]:
        # Check if the message itself is /convert or contains it
        is_convert = False
        if (m.text and "/convert" in m.text) or (m.caption and "/convert" in m.caption):
            is_convert = True
        
        # If not in message/caption, check if it's a reply and the reply text is /convert
        if not is_convert and m.reply_to_message:
             # This is tricky because the handler triggers on the media, not the /convert command message
             # We actually need a separate handler for the /convert command itself when it's a reply
             return # Let the command handler handle it if it's a reply

    if MY_PASS:
        check_pass = await pass_db.get_user_pass(m.chat.id)
        if check_pass== None:
            await m.reply_text("Nyaa~! Master, please login first using /login cmd! 🐾")
            return
        if check_pass != MY_PASS:
            await pass_db.delete_user(m.chat.id)
            return
            
    if not await db.is_user_exist(m.from_user.id):
        await db.add_user(m.from_user.id)
        await c.send_message(
            Var.BIN_CHANNEL,
            f"Nᴇᴡ Usᴇʀ Jᴏɪɴᴇᴅ : \n\n Nᴀᴍᴇ : [{m.from_user.first_name}](tg://user?id={m.from_user.id}) Sᴛᴀʀᴛᴇᴅ Yᴏᴜʀ Bᴏᴛ !!"
        )
        
    if Var.UPDATES_CHANNEL != "None":
        try:
            user = await c.get_chat_member(Var.UPDATES_CHANNEL, m.chat.id)
            if user.status == "kicked":
                await c.send_message(
                    chat_id=m.chat.id,
                    text="Nyaa~! Master, you are banned from using me! 😿",
                    disable_web_page_preview=True
                )
                return 
        except UserNotParticipant:
            await c.send_message(
                chat_id=m.chat.id,
                text="""<i>Nyaa~! Master, please join my updates channel to use me! 🐾✨</i>""",
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
            await m.reply_text(str(e))
            return
            
    try:
        # Verify BIN_CHANNEL is set
        if not Var.BIN_CHANNEL or Var.BIN_CHANNEL == 0:
            await m.reply_text("Nyaa~! Master, the BIN_CHANNEL is not configured! I can't save your files! 😿")
            return

        bin_id = int(str(Var.BIN_CHANNEL))
        # Try with and without -100 prefix logic
        try:
            log_msg = await m.forward(chat_id=bin_id)
        except Exception as forward_err:
            print(f"Forwarding failed with original ID: {forward_err}")
            try:
                # Try stripping -100 if it exists or adding it if it doesn't
                alt_bin_id = bin_id
                str_id = str(bin_id)
                if str_id.startswith("-100"):
                    alt_bin_id = int(str_id.replace("-100", "-"))
                elif str_id.startswith("-"):
                    alt_bin_id = int(str_id.replace("-", "-100"))
                
                print(f"Trying alternative ID: {alt_bin_id}")
                log_msg = await m.forward(chat_id=alt_bin_id)
            except Exception as alt_forward_err:
                print(f"Forwarding failed with alt ID: {alt_forward_err}")
                try:
                    log_msg = await m.copy(chat_id=bin_id)
                except Exception as copy_err:
                    print(f"Copying failed: {copy_err}")
                    await m.reply_text(f"Nyaa~! Master, I couldn't save the file to the BIN_CHANNEL. Please make sure I am an admin there with permission to post messages! 😿\n\nChannel ID: `{bin_id}`\nError: {copy_err}")
                    return
            
        file_hash = get_hash(log_msg)
        file_name = get_name(log_msg)
        
        # Ensure filenames have correct extensions if missing
        if m.video and not (file_name.lower().endswith('.mp4') or file_name.lower().endswith('.mkv')):
            file_name += '.mp4'
        elif m.photo and not (file_name.lower().endswith('.jpg') or file_name.lower().endswith('.png') or file_name.lower().endswith('.jpeg')):
            file_name += '.jpg'
            
        # Store file info in MongoDB for later retrieval
        await db.add_file({
            'file_unique_id': file_hash,
            'file_name': file_name,
            'message_id': log_msg.id,
            'file_size': get_media_file_size(m)
        })
            
        file_name_quoted = quote_plus(file_name)
        
        # Format the links so the filename (with extension) is the last part of the path
        # Pattern: /dl/{hash}/{filename.ext}
        stream_link = f"{Var.URL}watch/{str(log_msg.id)}/{file_name_quoted}?hash={file_hash}"
        online_link = f"{Var.URL}dl/{file_hash}/{file_name_quoted}"
        
        msg_text ="""
<b>Nyaa~! I've generated your link, master! 🐾✨</b>

<b>📧 ғɪʟᴇ ɴᴀᴍᴇ :- </b> <i><b>{}</b></i>

<b>📦 ғɪʟᴇ sɪᴢᴇ :- </b> <i><b>{}</b></i>

<b>💌 ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋ :- </b> <i><b>{}</b></i>

<b>🖥 ᴡᴀᴛᴄʜ ᴏɴʟɪɴᴇ :- </b> <i><b>{}</b></i>

<b>♻️ This link is permanent, I'll keep it safe for you! Nyaa~ 💖 ♻️\n\n❖ YouTube.com/OpusTechz</b>"""

        await log_msg.reply_text(text=f"**RᴇQᴜᴇꜱᴛᴇᴅ ʙʏ :** [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n**Uꜱᴇʀ ɪᴅ :** `{m.from_user.id}`\n**Stream ʟɪɴᴋ :** {stream_link}", disable_web_page_preview=False, quote=True)
        await m.reply_text(
            text=msg_text.format(file_name, humanbytes(get_media_file_size(m)), online_link, stream_link),
            quote=True,
            disable_web_page_preview=False,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ᴡᴀᴛᴄʜ ⚡", url=stream_link),
                                                InlineKeyboardButton('⚡ ᴅᴏᴡɴʟᴏᴀᴅ ⚡', url=online_link)]])
        )
    except Exception as e:
        print(f"Error in private_receive_handler: {e}")
        await m.reply_text(f"Nyaa~! Master, I encountered an error: {e} 😿")

@StreamBot.on_message(filters.command("convert") & filters.group & filters.reply)
async def convert_reply_handler(c: Client, m: Message):
    reply = m.reply_to_message
    if reply.document or reply.video or reply.audio or reply.photo or reply.voice:
        await private_receive_handler(c, reply)
    else:
        await m.reply_text("Nyaa~! Master, please reply to a video, image, or file with /convert! 🐾")

@StreamBot.on_message(filters.channel & ~filters.group & (filters.document | filters.video | filters.photo) & ~filters.forwarded, group=-1)
async def channel_receive_handler(bot, broadcast):
    if MY_PASS:
        check_pass = await pass_db.get_user_pass(broadcast.chat.id)
        if check_pass == None:
            await broadcast.reply_text("Login first using /login cmd \n don\'t know the pass? request it from @opustechz")
            return
        if check_pass != MY_PASS:
            await broadcast.reply_text("Wrong password, login again")
            await pass_db.delete_user(broadcast.chat.id)
            return
    if int(broadcast.chat.id) in Var.BANNED_CHANNELS:
        await bot.leave_chat(broadcast.chat.id)
        return
    try:
        bin_id = int(str(Var.BIN_CHANNEL))
        # Try with and without -100 prefix logic
        try:
            log_msg = await broadcast.forward(chat_id=bin_id)
        except Exception as forward_err:
            print(f"Forwarding failed with original ID: {forward_err}")
            try:
                # Try stripping -100 if it exists or adding it if it doesn't
                alt_bin_id = bin_id
                str_id = str(bin_id)
                if str_id.startswith("-100"):
                    alt_bin_id = int(str_id.replace("-100", "-"))
                elif str_id.startswith("-"):
                    alt_bin_id = int(str_id.replace("-", "-100"))
                
                print(f"Trying alternative ID: {alt_bin_id}")
                log_msg = await broadcast.forward(chat_id=alt_bin_id)
            except Exception as alt_forward_err:
                print(f"Forwarding failed with alt ID: {alt_forward_err}")
                try:
                    log_msg = await broadcast.copy(chat_id=bin_id)
                except Exception as copy_err:
                    print(f"Copying failed: {copy_err}")
                    await bot.send_message(chat_id=bin_id, text=f"**#ᴇʀʀᴏʀ_ᴛʀᴀᴄᴇʙᴀᴄᴋ:** `{copy_err}`", disable_web_page_preview=True)
                    return
            
        file_hash = get_hash(log_msg)
        file_name = get_name(log_msg)
        
        # Ensure filenames have correct extensions if missing
        if broadcast.video and not (file_name.lower().endswith('.mp4') or file_name.lower().endswith('.mkv')):
            file_name += '.mp4'
        elif broadcast.photo and not (file_name.lower().endswith('.jpg') or file_name.lower().endswith('.png') or file_name.lower().endswith('.jpeg')):
            file_name += '.jpg'
            
        # Store file info in MongoDB for later retrieval
        await db.add_file({
            'file_unique_id': file_hash,
            'file_name': file_name,
            'message_id': log_msg.id,
            'file_size': get_media_file_size(broadcast)
        })
            
        file_name_quoted = quote_plus(file_name)
        
        stream_link = f"{Var.URL}watch/{str(log_msg.id)}/{file_name_quoted}?hash={file_hash}"
        online_link = f"{Var.URL}dl/{file_hash}/{file_name_quoted}"
        
        await log_msg.reply_text(
            text=f"**Cʜᴀɴɴᴇʟ Nᴀᴍᴇ:** `{broadcast.chat.title}`\n**Cʜᴀɴɴᴇʟ ID:** `{broadcast.chat.id}`\n**Rᴇǫᴜᴇsᴛ ᴜʀʟ:** {stream_link}",
            quote=True
        )
        await bot.edit_message_reply_markup(
            chat_id=broadcast.chat.id,
            id=broadcast.id,
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("⚡ ᴡᴀᴛᴄʜ ⚡", url=stream_link),
                     InlineKeyboardButton('⚡ ᴅᴏᴡɴʟᴏᴀᴅ ⚡', url=online_link)] 
                ]
            )
        )
    except FloodWait as w:
        print(f"Sleeping for {str(w.x)}s")
        await asyncio.sleep(w.x)
        await bot.send_message(chat_id=Var.BIN_CHANNEL,
                             text=f"Gᴏᴛ FʟᴏᴏᴅWᴀɪᴛ ᴏғ {str(w.x)}s from {broadcast.chat.title}\n\n**Cʜᴀɴɴᴇʟ ID:** `{str(broadcast.chat.id)}`",
                             disable_web_page_preview=True)
    except Exception as e:
        await bot.send_message(chat_id=Var.BIN_CHANNEL, text=f"**#ᴇʀʀᴏʀ_ᴛʀᴀᴄᴇʙᴀᴄᴋ:** `{e}`", disable_web_page_preview=True)
        print(f"Cᴀɴ'ᴛ Eᴅɪᴛ Bʀᴏᴀᴅᴄᴀsᴛ Mᴇssᴀɢᴇ!\nEʀʀᴏʀ:  **Give me edit permission in updates and bin Chanell{e}**")
