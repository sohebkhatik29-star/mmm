import logging
import time
import re
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import ADMINS, INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp, get_readable_time
from math import ceil

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")
    data_parts = query.data.split("#")
    _, mode, chat, lst_msg_id, from_user = data_parts[:5]
    if mode == 'reject':
        await query.message.delete()
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been declined by our moderators.',
                               reply_to_message_id=int(lst_msg_id))
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    msg = query.message

    await query.answer('Processing...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been accepted by our moderators and will be added soon.',
                               reply_to_message_id=int(lst_msg_id))
    
    if mode == "video":
        mode_label = "🎬 Only Videos"
    elif mode == "document":
        mode_label = "📁 Only Documents"
    else:
        mode_label = "🎬 + 📁 Videos & Documents"

    await msg.edit(
        f"Starting Indexing...\n📌 Mode: <code>{mode_label}</code>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
    await index_files_to_db(int(lst_msg_id), chat, msg, bot, media_filter=mode)


@Client.on_message((filters.forwarded | (filters.regex(r"^(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$") & filters.text)) & filters.private & filters.incoming)
async def send_for_index(bot, message):
    user_id = message.from_user.id if message.from_user else None
    if user_id:
        try:
            from plugins.dump_manager import ADMIN_DUMP_STATE
            if user_id in ADMIN_DUMP_STATE or (await db.get_admin_dump_state(user_id)):
                return
        except Exception:
            pass
        try:
            from plugins.admin_fsub import ADMIN_FSUB_STATE
            if user_id in ADMIN_FSUB_STATE:
                return
        except Exception:
            pass

    if message.text:
        regex = re.compile(r"^(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    elif message.forward_from_chat and message.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = message.forward_from_message_id
        chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        return
    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        logger.exception(e)
        return await message.reply(f'Errors - {e}')
    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That Iam An Admin In The Channel, if channel is private')
    if k.empty:
        return await message.reply('This may be group and i am not a admin of the group.')

    if message.from_user.id in ADMINS:
        buttons = [
            [
                InlineKeyboardButton('🎬 Oɴʟʏ Vɪᴅᴇᴏ', callback_data=f'index#video#{chat_id}#{last_msg_id}#{message.from_user.id}'),
                InlineKeyboardButton('📁 Oɴʟʏ Dᴏᴄᴜᴍᴇɴᴛ', callback_data=f'index#document#{chat_id}#{last_msg_id}#{message.from_user.id}')
            ],
            [
                InlineKeyboardButton('🎬 + 📁 Bᴏᴛʜ (Vɪᴅᴇᴏ & Dᴏᴄ)', callback_data=f'index#all#{chat_id}#{last_msg_id}#{message.from_user.id}')
            ],
            [
                InlineKeyboardButton('🚫 Cʟᴏsᴇ', callback_data='close_data')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you Want To Index This Channel/ Group ?\n\nChat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>\n\nɴᴇᴇᴅ sᴇᴛsᴋɪᴘ 👉🏻 /setskip',
            reply_markup=reply_markup)

    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Make sure I am an admin in the chat and have permission to invite users.')
    else:
        link = f"@{message.forward_from_chat.username}"
    buttons = [
        [
            InlineKeyboardButton('🎬 Video', callback_data=f'index#video#{chat_id}#{last_msg_id}#{message.from_user.id}'),
            InlineKeyboardButton('📁 Doc', callback_data=f'index#document#{chat_id}#{last_msg_id}#{message.from_user.id}')
        ],
        [
            InlineKeyboardButton('🎬 + 📁 Both', callback_data=f'index#all#{chat_id}#{last_msg_id}#{message.from_user.id}')
        ],
        [
            InlineKeyboardButton('Reject Index', callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(LOG_CHANNEL,
                           f'#IndexRequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username - <code> {chat_id}</code>\nLast Message ID - <code>{last_msg_id}</code>\nInviteLink - {link}',
                           reply_markup=reply_markup)
    await message.reply('ThankYou For the Contribution, Wait For My Moderators to verify the files.')


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("Skip number should be an integer.")
        await message.reply(f"Successfully set SKIP number as {skip}")
        temp.CURRENT = int(skip)
    else:
        await message.reply("Give me a skip number")

def get_progress_bar(percent, length=10):
    """Creates an emoji-based progress bar."""
    filled = int(length * percent / 100)
    unfilled = length - filled
    return '🟩' * filled + '⬜️' * unfilled

async def find_first_message_id(bot, chat, start_id, end_id):
    """Binary search to quickly find where existing messages start in a channel."""
    if start_id >= end_id:
        return start_id
    low = start_id
    high = end_id
    first_found = end_id

    while low <= high:
        mid = (low + high) // 2
        slice_ids = list(range(mid, min(mid + 50, high + 1)))
        try:
            msgs = await bot.get_messages(chat, slice_ids)
            if not isinstance(msgs, list):
                msgs = [msgs]
            found = False
            for m in msgs:
                if m and not m.empty:
                    first_found = min(first_found, m.id)
                    found = True
                    break
            if found:
                high = mid - 1
            else:
                low = mid + 50
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception:
            low += 50

    return max(start_id, min(first_found, end_id))

async def index_files_to_db(lst_msg_id, chat, msg, bot, media_filter="all"):
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    start_time = time.time()
    last_edit_time = 0

    if media_filter == "video":
        allowed_media = [enums.MessageMediaType.VIDEO]
        mode_label = "🎬 Only Videos"
    elif media_filter == "document":
        allowed_media = [enums.MessageMediaType.DOCUMENT]
        mode_label = "📁 Only Documents"
    else:
        allowed_media = [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]
        mode_label = "🎬 + 📁 Videos & Documents"

    async with lock:
        try:
            temp.CANCEL = False
            start_skip = temp.CURRENT

            await msg.edit(
                f"📊 <b>Indexing Started...</b>\n"
                f"📌 Mode: <code>{mode_label}</code>\n"
                f"💬 Chat: <code>{chat}</code>\n"
                f"⏰ Please wait, fetching media...",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='index_cancel')]])
            )

            # Strategy 1: Reverse pagination from lst_msg_id downwards (or get_chat_history)
            # Since files are at/near lst_msg_id, we fetch backward in batches of 200:
            # e.g., lst_msg_id -> lst_msg_id - 200 -> lst_msg_id - 400 ...
            # This ensures we get all files immediately with 0 deleted-message delays!
            
            curr_id = lst_msg_id
            BATCH_SIZE = 200
            empty_streak = 0
            scanned_total = 0

            while curr_id > start_skip:
                if temp.CANCEL:
                    break

                batch_end = curr_id
                batch_start = max(start_skip + 1, curr_id - BATCH_SIZE + 1)
                message_ids = list(range(batch_start, batch_end + 1))
                curr_id = batch_start - 1

                try:
                    messages = await bot.get_messages(chat, message_ids)
                    if not isinstance(messages, list):
                        messages = [messages]
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                    try:
                        messages = await bot.get_messages(chat, message_ids)
                        if not isinstance(messages, list):
                            messages = [messages]
                    except Exception:
                        messages = []
                except Exception as e:
                    errors += len(message_ids)
                    continue

                batch_save_tasks = []
                batch_media_count = 0

                for message in reversed(messages):
                    scanned_total += 1
                    try:
                        if not message or message.empty:
                            deleted += 1
                            continue

                        if not message.media:
                            no_media += 1
                            continue
                        elif message.media not in allowed_media:
                            unsupported += 1
                            continue

                        media = getattr(message, message.media.value, None)
                        if not media:
                            unsupported += 1
                            continue
                        
                        batch_media_count += 1
                        media.file_type = message.media.value
                        media.caption = message.caption
                        batch_save_tasks.append(save_file(media))
                    except Exception:
                        errors += 1
                        continue

                if batch_media_count == 0:
                    empty_streak += 1
                else:
                    empty_streak = 0

                if batch_save_tasks:
                    results = await asyncio.gather(*batch_save_tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            errors += 1
                        else:
                            ok, code = result
                            if ok:
                                total_files += 1
                            elif code == 0:
                                duplicate += 1
                            elif code == 2:
                                errors += 1

                # Update UI every 4 seconds
                if time.time() - last_edit_time >= 4 or curr_id <= start_skip:
                    elapsed = time.time() - start_time
                    try:
                        await msg.edit(
                            f"📊 <b>Indexing in Progress</b>\n"
                            f"📌 Mode: <code>{mode_label}</code>\n\n"
                            f"💾 <b>Saved Files:</b> <code>{total_files}</code>\n"
                            f"♻️ <b>Duplicates:</b> <code>{duplicate}</code>\n"
                            f"🔍 <b>Messages Scanned:</b> <code>{scanned_total}</code>\n"
                            f"🗑️ <b>Deleted/Empty:</b> <code>{deleted}</code>\n"
                            f"⏩ <b>Other Skipped:</b> <code>{no_media + unsupported}</code>\n"
                            f"⚠️ <b>Errors:</b> <code>{errors}</code>\n"
                            f"⏱️ <b>Elapsed:</b> <code>{get_readable_time(elapsed)}</code>",
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='index_cancel')]])
                        )
                        last_edit_time = time.time()
                    except FloodWait as e:
                        await asyncio.sleep(e.value + 1)
                    except Exception:
                        pass

                # If 10 consecutive batches (2000 messages) have 0 media and we already saved files, stop or continue
                # We stop after 20 consecutive empty batches (4000 messages) to avoid scanning empty channel start
                if empty_streak >= 25 and total_files > 0:
                    logger.info("Reached empty message gap of 5000 messages after finding files, indexing complete.")
                    break

            elapsed = time.time() - start_time
            status_title = "🚫 Indexing Cancelled!" if temp.CANCEL else "✅ Indexing Completed!"

            try:
                await msg.edit(
                    f"{status_title}\n"
                    f"📌 Mode: <code>{mode_label}</code>\n\n"
                    f"💾 <b>Total Saved:</b> <code>{total_files}</code>\n"
                    f"♻️ <b>Duplicates:</b> <code>{duplicate}</code>\n"
                    f"🔍 <b>Total Scanned:</b> <code>{scanned_total}</code>\n"
                    f"🗑️ <b>Deleted/Empty:</b> <code>{deleted}</code>\n"
                    f"⏩ <b>Other Skipped:</b> <code>{no_media + unsupported}</code>\n"
                    f"⚠️ <b>Errors:</b> <code>{errors}</code>\n"
                    f"⏱️ <b>Total Time:</b> <code>{get_readable_time(elapsed)}</code>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Close', callback_data='close_data')]])
                )
            except Exception:
                pass

        except Exception as e:
            logger.exception("Index error: %s", e)
            try:
                await msg.edit(
                    f"❌ Error: <code>{e}</code>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Close', callback_data='close_data')]])
                )
            except Exception:
                pass

