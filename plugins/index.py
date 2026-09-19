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


@Client.on_message((filters.forwarded | (filters.regex(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def send_for_index(bot, message):
    if message.text:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return await message.reply('Invalid link')
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
            current_skip = temp.CURRENT
            temp.CANCEL = False

            await msg.edit(
                f"📊 Indexing Starting...\n"
                f"📌 Mode: <code>{mode_label}</code>\n"
                f"💬 Chat: <code>{chat}</code>\n"
                f"⏰ Elapsed: <code>0s</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='index_cancel')]])
            )

            # Strategy 1: Use get_chat_history to fetch ONLY existing messages directly (Ultra-fast)
            use_history = True
            processed_count = 0
            save_tasks = []

            try:
                async for message in bot.get_chat_history(chat):
                    if temp.CANCEL:
                        break
                    if message.id <= current_skip:
                        break
                    if lst_msg_id and message.id > lst_msg_id:
                        continue

                    processed_count += 1
                    try:
                        if message.empty:
                            deleted += 1
                            continue
                        elif not message.media:
                            no_media += 1
                            continue
                        elif message.media not in allowed_media:
                            unsupported += 1
                            continue
                        media = getattr(message, message.media.value, None)
                        if not media:
                            unsupported += 1
                            continue
                        media.file_type = message.media.value
                        media.caption = message.caption
                        save_tasks.append(save_file(media))
                    except Exception:
                        errors += 1
                        continue

                    # Process save tasks in batches of 40
                    if len(save_tasks) >= 40:
                        results = await asyncio.gather(*save_tasks, return_exceptions=True)
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
                        save_tasks = []

                    # Update UI at most once every 4 seconds to avoid Telegram rate-limits
                    if time.time() - last_edit_time >= 4:
                        elapsed = time.time() - start_time
                        try:
                            await msg.edit(
                                f"📊 Indexing in Progress...\n"
                                f"📌 Mode: <code>{mode_label}</code>\n\n"
                                f"📦 Messages Scanned: <code>{processed_count}</code>\n"
                                f"💾 Files Saved: <code>{total_files}</code>\n"
                                f"♻️ Duplicates: <code>{duplicate}</code>\n"
                                f"⏩ Skipped/Other: <code>{no_media + unsupported}</code>\n"
                                f"⚠️ Errors: <code>{errors}</code>\n"
                                f"⏱️ Elapsed: <code>{get_readable_time(elapsed)}</code>",
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='index_cancel')]])
                            )
                            last_edit_time = time.time()
                        except FloodWait as e:
                            await asyncio.sleep(e.value + 1)
                        except Exception:
                            pass

                # Flush remaining save tasks
                if save_tasks:
                    results = await asyncio.gather(*save_tasks, return_exceptions=True)
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
                    save_tasks = []

            except Exception as hist_err:
                logger.warning("get_chat_history error: %s, using batch fallback...", hist_err)
                use_history = False

            # Strategy 2: Fallback to get_messages batching if get_chat_history failed
            if not use_history and not temp.CANCEL:
                BATCH_SIZE = 200
                current = temp.CURRENT
                total_messages = lst_msg_id
                total_fetch = max(1, lst_msg_id - current)
                batches = ceil(total_fetch / BATCH_SIZE)

                for batch in range(batches):
                    if temp.CANCEL:
                        break
                    start_id = current + 1
                    end_id = min(current + BATCH_SIZE, lst_msg_id)
                    message_ids = list(range(start_id, end_id + 1))
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
                        current += len(message_ids)
                        continue

                    batch_save_tasks = []
                    for message in messages:
                        current += 1
                        try:
                            if message.empty:
                                deleted += 1
                                continue
                            elif not message.media:
                                no_media += 1
                                continue
                            elif message.media not in allowed_media:
                                unsupported += 1
                                continue
                            media = getattr(message, message.media.value, None)
                            if not media:
                                unsupported += 1
                                continue
                            media.file_type = message.media.value
                            media.caption = message.caption
                            batch_save_tasks.append(save_file(media))
                        except Exception:
                            errors += 1
                            continue

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

                    if time.time() - last_edit_time >= 4 or batch == batches - 1:
                        elapsed = time.time() - start_time
                        progress = current - temp.CURRENT
                        percentage = (progress / total_fetch) * 100 if total_fetch > 0 else 100
                        progress_bar = get_progress_bar(int(percentage))
                        try:
                            await msg.edit(
                                f"📊 Indexing Progress 📦 Batch {batch + 1}/{batches}\n"
                                f"📌 Mode: <code>{mode_label}</code>\n"
                                f"{progress_bar} <code>{percentage:.1f}%</code>\n\n"
                                f"Total Messages: <code>{total_messages}</code>\n"
                                f"Fetched: <code>{current}</code>\n"
                                f"Saved: <code>{total_files}</code>\n"
                                f"Duplicates: <code>{duplicate}</code>\n"
                                f"Deleted: <code>{deleted}</code>\n"
                                f"Non-Media/Skipped: <code>{no_media + unsupported}</code>\n"
                                f"Errors: <code>{errors}</code>\n"
                                f"⏱️ Elapsed: <code>{get_readable_time(elapsed)}</code>",
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='index_cancel')]])
                            )
                            last_edit_time = time.time()
                        except FloodWait as e:
                            await asyncio.sleep(e.value + 1)
                        except Exception:
                            pass

            elapsed = time.time() - start_time
            status_title = "🚫 Indexing Cancelled!" if temp.CANCEL else "✅ Indexing Completed!"

            try:
                await msg.edit(
                    f"{status_title}\n"
                    f"📌 Mode: <code>{mode_label}</code>\n\n"
                    f"💾 Saved: <code>{total_files}</code>\n"
                    f"♻️ Duplicates: <code>{duplicate}</code>\n"
                    f"⏩ Skipped/Other: <code>{no_media + unsupported}</code>\n"
                    f"⚠️ Errors: <code>{errors}</code>\n"
                    f"⏱️ Total Time: <code>{get_readable_time(elapsed)}</code>",
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

