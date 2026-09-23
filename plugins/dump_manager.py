import re
import time
import asyncio
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)
from pyrogram.errors import (
    FloodWait,
    ChatAdminRequired,
    UserNotParticipant,
    ChannelInvalid,
    PeerIdInvalid,
    MessageNotModified,
    RPCError
)
from info import ADMINS, INITIAL_ADMINS, MULTIPLE_DB, CUSTOM_FILE_CAPTION, COLLECTION_NAME
from database.ia_filterdb import Media, Media2, db as media_db, db2 as media_db2
from database.users_chats_db import db
from utils import get_size, clean_filename

logger = logging.getLogger(__name__)

# State for admin interactive prompts: {admin_id: {"action": str, "prompt_msg_id": int}}
ADMIN_DUMP_STATE = {}

# Active dump state dictionary
CURRENT_DUMP = {
    "is_running": False,
    "target_channel_id": None,
    "target_channel_title": None,
    "total_files": 0,
    "dumped_files": 0,
    "failed_files": 0,
    "start_time": None,
    "cancel_requested": False,
    "task": None,
    "status_msg_id": None,
    "status_chat_id": None,
    "admin_id": None
}


def is_admin(user_id: int) -> bool:
    try:
        uid = int(user_id)
        if uid in ADMINS or str(uid) in [str(a) for a in ADMINS]:
            return True
        if uid in INITIAL_ADMINS or str(uid) in [str(a) for a in INITIAL_ADMINS]:
            return True
        return False
    except Exception:
        return False


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}h {minutes:02d}m {secs:02d}s"
    return f"{minutes:02d}m {secs:02d}s"


def create_progress_bar(completed: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return "░" * length
    percent = completed / total
    filled = int(round(length * percent))
    filled = min(filled, length)
    bar = "█" * filled + "░" * (length - filled)
    return bar


async def safe_edit_or_replace(
    client: Client,
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup = None,
    disable_web_page_preview: bool = True
):
    try:
        return await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        try:
            await message.delete()
        except Exception:
            pass
        return await client.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            parse_mode=enums.ParseMode.HTML
        )


async def get_total_db_files_count() -> int:
    try:
        count = await Media.count_documents({})
        if MULTIPLE_DB:
            count += await Media2.count_documents({})
        return count
    except Exception as e:
        logger.error(f"Error counting DB files: {e}")
        return 0


# =========================================================================
# Main Dump Settings Panel Callback & Command
# =========================================================================

@Client.on_message(filters.command(["dump", "dump_settings", "dumpfiles"]) & filters.private)
async def dump_settings_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> This command is restricted to Bot Administrators only.")
    
    ADMIN_DUMP_STATE.pop(message.from_user.id, None)
    await db.clear_admin_dump_state(message.from_user.id)
    await show_dump_panel(client, message)


@Client.on_callback_query(filters.regex(r"^dump_settings_panel$"))
async def dump_settings_panel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    ADMIN_DUMP_STATE.pop(query.from_user.id, None)
    await db.clear_admin_dump_state(query.from_user.id)
    await show_dump_panel(client, query.message)
    await query.answer()


async def show_dump_panel(client: Client, message: Message):
    total_db_files = await get_total_db_files_count()
    custom_caption = await db.get_dump_caption()
    caption_status = "Custom" if custom_caption else "Default"
    sort_mode = await db.get_dump_sort_mode()
    sort_label = "🔤 Name Wise (A to Z)" if sort_mode == "name" else "🆕 Latest Added First (New to Old)"
    sort_btn_text = f"🔀 Sort: {'🔤 A-Z' if sort_mode == 'name' else '🆕 Latest First'}"
    
    if CURRENT_DUMP["is_running"]:
        elapsed = time.time() - CURRENT_DUMP["start_time"]
        total = CURRENT_DUMP["total_files"]
        dumped = CURRENT_DUMP["dumped_files"]
        failed = CURRENT_DUMP["failed_files"]
        pct = (dumped + failed) / total * 100 if total > 0 else 0
        pbar = create_progress_bar(dumped + failed, total)
        
        text = (
            "📦 <b><u>Database Channel Dump Control</u></b>\n\n"
            "🟢 <b>Status:</b> <b>Dumping In Progress...</b>\n\n"
            f"📢 <b>Target Channel:</b> <code>{CURRENT_DUMP['target_channel_title']}</code> (<code>{CURRENT_DUMP['target_channel_id']}</code>)\n"
            f"📊 <b>Total Files:</b> <code>{total:,}</code>\n"
            f"✅ <b>Uploaded:</b> <code>{dumped:,}</code>\n"
            f"❌ <b>Failed / Skipped:</b> <code>{failed:,}</code>\n"
            f"⏳ <b>Remaining:</b> <code>{max(0, total - dumped - failed):,}</code>\n"
            f"📈 <b>Progress:</b> <code>{pct:.1f}%</code> [{pbar}]\n"
            f"⏱ <b>Elapsed Time:</b> <code>{format_duration(elapsed)}</code>\n\n"
            f"⚡ <b>Sort Order:</b> <code>{sort_label}</code>"
        )
        buttons = [
            [
                InlineKeyboardButton("🔄 Refresh Status", callback_data="dump_refresh_status"),
                InlineKeyboardButton("🛑 Stop Dump", callback_data="dump_stop_confirm")
            ],
            [
                InlineKeyboardButton("« Back to Admin Menu", callback_data="admin_settings")
            ]
        ]
    else:
        text = (
            "📦 <b><u>Database Channel Dump Management</u></b>\n\n"
            "Welcome to the Database Export & Channel Dump Manager.\n\n"
            f"📂 <b>Total Files in MongoDB:</b> <code>{total_db_files:,} files</code>\n"
            f"🔀 <b>Current Sort Order:</b> <code>{sort_label}</code>\n"
            f"📝 <b>Dump Caption:</b> <code>{caption_status}</code>\n"
            "⚪ <b>Current Status:</b> <code>Idle (No active dump)</code>\n\n"
            "💡 <b>Sort Options:</b>\n"
            "• <b>🆕 Latest Added First (Default):</b> Jo movies abhi nayi add hui hain (`Mardaani 3`, `Stree 2` etc.) wo pehle aayengi.\n"
            "• <b>🔤 Name Wise (A to Z):</b> Movie ki saari qualities (480p, 720p, 1080p) ek sath line se aayengi."
        )
        buttons = [
            [
                InlineKeyboardButton("🚀 Start Dump", callback_data="dump_start_prompt"),
                InlineKeyboardButton(sort_btn_text, callback_data="dump_toggle_sort")
            ],
            [
                InlineKeyboardButton("📝 ꜱᴇᴛ ᴅᴜᴍᴘ ᴄᴀᴘᴛɪᴏɴ", callback_data="dump_caption_menu"),
                InlineKeyboardButton("📊 Dump Status", callback_data="dump_refresh_status")
            ],
            [
                InlineKeyboardButton("« Back to Admin Menu", callback_data="admin_settings"),
                InlineKeyboardButton("⇋ Home ⇋", callback_data="start")
            ]
        ]
        
    await safe_edit_or_replace(client, message, text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^dump_toggle_sort$"))
async def dump_toggle_sort_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    current_mode = await db.get_dump_sort_mode()
    new_mode = "name" if current_mode == "latest" else "latest"
    await db.set_dump_sort_mode(new_mode)
    
    label = "🔤 Name Wise (A to Z)" if new_mode == "name" else "🆕 Latest Added First (New to Old)"
    await query.answer(f"Sort Order: {label}", show_alert=True)
    await show_dump_panel(client, query.message)


# =========================================================================
# Step 1: Prompt for Target Channel
# =========================================================================

@Client.on_callback_query(filters.regex(r"^dump_start_prompt$"))
async def dump_start_prompt_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    if CURRENT_DUMP["is_running"]:
        return await query.answer("⚠️ A dump process is already running!", show_alert=True)
    
    state_payload = {
        "action": "await_dump_channel",
        "prompt_msg_id": query.message.id
    }
    ADMIN_DUMP_STATE[query.from_user.id] = state_payload
    await db.set_admin_dump_state(query.from_user.id, state_payload)
    
    text = (
        "📤 <b><u>Target Channel Setup for Dump</u></b>\n\n"
        "👉 <b>Please forward any message from your target channel.</b>\n\n"
        "<i>(Or send the Channel ID like <code>-100xxxxxxxxxx</code> or @channel_username)</i>\n\n"
        "⚠️ <b>Important Requirements:</b>\n"
        "• Bot <b>MUST be an Admin</b> in that channel.\n"
        "• Bot must have <b>'Post Messages'</b> permission.\n\n"
        "Type <code>/cancel</code> to cancel."
    )
    buttons = [
        [InlineKeyboardButton("❌ Cancel", callback_data="dump_settings_panel")]
    ]
    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


# =========================================================================
# Step 2: Custom Dump Caption Management
# =========================================================================

@Client.on_callback_query(filters.regex(r"^dump_caption_menu$"))
async def dump_caption_menu_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    ADMIN_DUMP_STATE.pop(query.from_user.id, None)
    await db.clear_admin_dump_state(query.from_user.id)
    custom_caption = await db.get_dump_caption()
    
    if custom_caption:
        text = (
            "📝 <b><u>Dump File Caption Settings</u></b>\n\n"
            "✅ <b>Status:</b> Custom Caption is <b>ACTIVE</b>\n\n"
            f"<b>Current Dump Caption:</b>\n<blockquote>{custom_caption}</blockquote>\n\n"
            "📌 <b>Available Variables:</b>\n"
            "• <code>{file_name}</code> - Name of the movie / file\n"
            "• <code>{file_size}</code> - File size (e.g. 1.2 GB)\n"
            "• <code>{file_caption}</code> - Original caption from database"
        )
        buttons = [
            [
                InlineKeyboardButton("🔄 Change Caption", callback_data="dump_caption_set"),
                InlineKeyboardButton("🗑️ Reset to Default", callback_data="dump_caption_reset")
            ],
            [
                InlineKeyboardButton("« Back to Dump Menu", callback_data="dump_settings_panel")
            ]
        ]
    else:
        text = (
            "📝 <b><u>Dump File Caption Settings</u></b>\n\n"
            "⚙️ <b>Status:</b> Using <b>DEFAULT / ORIGINAL CAPTION</b>\n\n"
            "Files dumped to your channel will use their original name and size or bot caption.\n\n"
            "📌 <b>Available Variables:</b>\n"
            "• <code>{file_name}</code> - File Name\n"
            "• <code>{file_size}</code> - File Size\n"
            "• <code>{file_caption}</code> - Original Caption\n\n"
            "Click below to set a custom caption for all dumped files:"
        )
        buttons = [
            [InlineKeyboardButton("➕ Set Custom Caption", callback_data="dump_caption_set")],
            [InlineKeyboardButton("« Back to Dump Menu", callback_data="dump_settings_panel")]
        ]
        
    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^dump_caption_set$"))
async def dump_caption_set_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    state_payload = {
        "action": "await_dump_caption",
        "prompt_msg_id": query.message.id
    }
    ADMIN_DUMP_STATE[query.from_user.id] = state_payload
    await db.set_admin_dump_state(query.from_user.id, state_payload)
    
    text = (
        "📝 <b><u>Set Custom Dump File Caption</u></b>\n\n"
        "👉 <b>Apna naya Dump Caption yahan type karke bhejein.</b>\n\n"
        "📌 <b>Available Variables:</b>\n"
        "• <code>{file_name}</code> - Movie name\n"
        "• <code>{file_size}</code> - File size (e.g. 700MB)\n"
        "• <code>{file_caption}</code> - Original caption\n\n"
        "<b>Example:</b>\n"
        "<code>🎬 {file_name}\n📦 Size: {file_size}\n\n🌟 Join @YourChannel</code>\n\n"
        "Send <code>/cancel</code> to cancel."
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="dump_caption_menu")]]
    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^dump_caption_reset$"))
async def dump_caption_reset_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await db.delete_dump_caption()
    await query.answer("✅ Dump caption reset to default!", show_alert=True)
    
    ADMIN_DUMP_STATE.pop(query.from_user.id, None)
    await db.clear_admin_dump_state(query.from_user.id)
    text = (
        "📝 <b><u>Dump File Caption Settings</u></b>\n\n"
        "⚙️ <b>Status:</b> Reset to <b>DEFAULT CAPTION</b>\n\n"
        "Custom dump caption successfully remove ho gaya hai."
    )
    buttons = [
        [InlineKeyboardButton("➕ Set Custom Caption", callback_data="dump_caption_set")],
        [InlineKeyboardButton("« Back to Dump Menu", callback_data="dump_settings_panel")]
    ]
    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))


# =========================================================================
# Unified Input Handler for Dump Actions (Group 4)
# =========================================================================

@Client.on_message(filters.private & ~filters.bot & filters.incoming, group=4)
async def handle_dump_admin_inputs(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return

    # Check if this admin is in dump state
    state_info = ADMIN_DUMP_STATE.get(user_id)
    if not state_info:
        state_info = await db.get_admin_dump_state(user_id)
        if state_info:
            ADMIN_DUMP_STATE[user_id] = state_info
    
    if not state_info:
        return

    if not is_admin(user_id):
        ADMIN_DUMP_STATE.pop(user_id, None)
        await db.clear_admin_dump_state(user_id)
        return

    try:
        message.stop_propagation()
    except Exception:
        pass

    action = state_info.get("action")
    prompt_msg_id = state_info.get("prompt_msg_id")

    # Cancel command check
    if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
        ADMIN_DUMP_STATE.pop(user_id, None)
        await db.clear_admin_dump_state(user_id)
        text = "🚫 <b>Dump operation cancelled.</b>"
        buttons = [[InlineKeyboardButton("« Back to Dump Menu", callback_data="dump_settings_panel")]]
        return await message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )

    # -----------------------------------------------------------------
    # State 1: Awaiting Custom Dump Caption
    # -----------------------------------------------------------------
    if action == "await_dump_caption":
        raw_caption = message.text.html if (message.text and hasattr(message.text, 'html')) else (message.text or message.caption or "")
        if not raw_caption:
            return await message.reply_text(
                "❌ <b>Invalid Input!</b>\n\nPlease send text for the caption.\nType /cancel to cancel."
            )

        try:
            await db.set_dump_caption(raw_caption)
            ADMIN_DUMP_STATE.pop(user_id, None)
            await db.clear_admin_dump_state(user_id)

            success_text = (
                "✅ <b><u>Dump File Caption Saved Successfully!</u></b>\n\n"
                f"<b>Saved Preview:</b>\n<blockquote>{raw_caption}</blockquote>\n\n"
                "Ab jab bhi aap dump chalu karenge, files isi custom caption ke sath channel me upload hongi."
            )
            buttons = [
                [InlineKeyboardButton("📝 View Caption Menu", callback_data="dump_caption_menu")],
                [InlineKeyboardButton("« Back to Dump Menu", callback_data="dump_settings_panel")]
            ]
            return await message.reply_text(
                text=success_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            logger.exception("Error saving dump caption: %s", e)
            return await message.reply_text(f"❌ <b>Error:</b> <code>{e}</code>")

    # -----------------------------------------------------------------
    # State 2: Awaiting Target Channel
    # -----------------------------------------------------------------
    elif action == "await_dump_channel":
        target_chat_identifier = None

        if message.forward_from_chat:
            target_chat_identifier = message.forward_from_chat.id
        elif hasattr(message, "forward_origin") and message.forward_origin and hasattr(message.forward_origin, "chat") and message.forward_origin.chat:
            target_chat_identifier = message.forward_origin.chat.id
        elif message.text:
            raw_text = message.text.strip()
            # Numeric Channel ID (e.g. -1004372863755)
            if re.match(r"^-100\d+$", raw_text) or re.match(r"^-\d+$", raw_text):
                target_chat_identifier = int(raw_text)
            # Username (@channel)
            elif raw_text.startswith("@"):
                target_chat_identifier = raw_text
            # Private invite links
            elif "t.me/+" in raw_text or "t.me/joinchat/" in raw_text:
                return await message.reply_text(
                    "⚠️ <b>Private Invite Link Detected!</b>\n\n"
                    "Telegram bot private invite links (<code>t.me/+...</code>) se direct channel access nahi kar sakta.\n\n"
                    "👉 <b>Channel kaise connect karein:</b>\n"
                    "1. Bot ko apne target channel me <b>Administrator</b> banayein (sirf Subscriber nahi, Admin rights me <b>'Post Messages'</b> ON hona zaroori hai).\n"
                    "2. Fir channel se koi message yahan <b>Forward</b> karein, ya Channel ID (jaise <code>-1004372863755</code>) bhejein.\n\n"
                    "<i>Type /cancel to cancel.</i>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="dump_settings_panel")]])
                )
            # Public t.me link
            elif "t.me/" in raw_text:
                clean_url = raw_text.split("?")[0].rstrip("/")
                parts = clean_url.split("/")
                if parts:
                    last_part = parts[-1]
                    if not last_part.isdigit():
                        target_chat_identifier = f"@{last_part}"
                    else:
                        target_chat_identifier = clean_url
            else:
                target_chat_identifier = raw_text

        if not target_chat_identifier:
            return await message.reply_text(
                "❌ <b>Invalid Input!</b>\n\n"
                "Kripya target channel se koi message forward karein ya Channel ID (jaise <code>-1004372863755</code>) bhejein.\n\n"
                "Type /cancel to cancel.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="dump_settings_panel")]])
            )

        # Delete user's forwarded message or text input to keep chat clean
        try:
            await message.delete()
        except Exception:
            pass

        # Use and update prompt message if available to avoid stacking messages
        status_msg = None
        if prompt_msg_id:
            try:
                status_msg = await client.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_msg_id,
                    text="🔍 <b>Verifying Channel & Admin Permissions...</b> Please wait...",
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                status_msg = None

        if not status_msg:
            status_msg = await message.reply_text("🔍 <b>Verifying Channel & Admin Permissions...</b> Please wait...")

        try:
            target_chat = await client.get_chat(target_chat_identifier)
        except Exception as e:
            logger.error(f"Failed to fetch chat {target_chat_identifier}: {e}")
            err_text = (
                "❌ <b>Channel Access Failed!</b>\n\n"
                f"<b>Error Details:</b> <code>{e}</code>\n\n"
                "👉 <b>Important Requirements:</b>\n"
                "1. Bot ko us channel me <b>Administrator</b> banayein ('Post Messages' permission ke sath).\n"
                "<i>(Note: Channel me sirf Member/Subscriber add karne se bot ko access nahi milta. Settings ➔ Administrators ➔ Add Admin me jaake bot ko Administrator banayein!)</i>\n"
                "2. Channel ID sahi check karein.\n\n"
                "Bot ko Admin banane ke baad dubara ID bhejein ya Try Again karein."
            )
            buttons = [
                [InlineKeyboardButton("🔄 Try Again", callback_data="dump_start_prompt")],
                [InlineKeyboardButton("« Back to Dump Menu", callback_data="dump_settings_panel")]
            ]
            return await status_msg.edit_text(err_text, reply_markup=InlineKeyboardMarkup(buttons))

        # Check bot admin status in target chat
        try:
            bot_member = await client.get_chat_member(target_chat.id, "me")
            if bot_member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return await status_msg.edit_text(
                    f"❌ <b>Bot is NOT an Admin in {target_chat.title}!</b>\n\n"
                    f"Bot channel me subscriber/member hai, lekin <b>Administrator</b> nahi hai!\n\n"
                    f"👉 <b>Channel Settings ➔ Administrators ➔ Add Administrator</b> me jayein, bot ko select karein aur <b>'Post Messages'</b> ON karein.\n\n"
                    f"Fir dubara message forward karein ya ID bhejein.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Try Again", callback_data="dump_start_prompt")],
                        [InlineKeyboardButton("« Back to Dump Menu", callback_data="dump_settings_panel")]
                    ])
                )
            
            can_post = True
            if bot_member.status == enums.ChatMemberStatus.ADMINISTRATOR and hasattr(bot_member, "privileges") and bot_member.privileges:
                can_post = bool(bot_member.privileges.can_post_messages)
                
            if not can_post:
                return await status_msg.edit_text(
                    f"❌ <b>Missing Permission: Post Messages!</b>\n\n"
                    f"Bot <b>{target_chat.title}</b> me Admin to hai, lekin <b>'Post Messages'</b> permission band hai.\n\n"
                    f"👉 Channel Settings ➔ Administrators ➔ Bot Permissions me <b>'Post Messages'</b> ON karke dubara try karein.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Try Again", callback_data="dump_start_prompt")],
                        [InlineKeyboardButton("« Back to Dump Menu", callback_data="dump_settings_panel")]
                    ])
                )
        except Exception as e:
            logger.error(f"Bot permission check error: {e}")
            return await status_msg.edit_text(
                f"❌ <b>Admin Check Error:</b> <code>{e}</code>\n\n"
                f"Make sure bot is an Administrator in <b>{target_chat.title}</b>!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Try Again", callback_data="dump_start_prompt")],
                    [InlineKeyboardButton("« Back to Dump Menu", callback_data="dump_settings_panel")]
                ])
            )

        ADMIN_DUMP_STATE.pop(user_id, None)
        await db.clear_admin_dump_state(user_id)
        total_files = await get_total_db_files_count()
        sort_mode = await db.get_dump_sort_mode()
        sort_label = "🔤 Name Wise (A to Z)" if sort_mode == "name" else "🆕 Latest Added First (New to Old)"

        confirm_text = (
            "✅ <b><u>Channel Verified Successfully!</u></b>\n\n"
            f"📢 <b>Target Channel:</b> <code>{target_chat.title}</code>\n"
            f"🆔 <b>Channel ID:</b> <code>{target_chat.id}</code>\n"
            f"📂 <b>Total Files to Dump:</b> <code>{total_files:,} files</code>\n"
            f"🔀 <b>Sort Order:</b> <code>{sort_label}</code>\n\n"
            "Are you ready to start dumping all stored files from the database into this channel?"
        )
        buttons = [
            [
                InlineKeyboardButton("✅ Yes, Start Dump", callback_data=f"dump_confirm_start#{target_chat.id}#{target_chat.title[:20]}"),
                InlineKeyboardButton("❌ No, Cancel", callback_data="dump_settings_panel")
            ]
        ]
        return await status_msg.edit_text(confirm_text, reply_markup=InlineKeyboardMarkup(buttons))


# =========================================================================
# Step 3: Confirm Start Dump & Worker Execution
# =========================================================================

@Client.on_callback_query(filters.regex(r"^dump_confirm_start#"))
async def dump_confirm_start_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    if CURRENT_DUMP["is_running"]:
        return await query.answer("⚠️ A dump task is already running!", show_alert=True)
    
    parts = query.data.split("#")
    target_channel_id = int(parts[1])
    target_channel_title = parts[2] if len(parts) > 2 else "Channel"
    
    total_files = await get_total_db_files_count()
    logger.info(f"Total files in DB: {total_files}")
    if total_files == 0:
        return await query.answer("❌ No files found in database to dump!", show_alert=True)

    CURRENT_DUMP["is_running"] = True
    CURRENT_DUMP["target_channel_id"] = target_channel_id
    CURRENT_DUMP["target_channel_title"] = target_channel_title
    CURRENT_DUMP["total_files"] = total_files
    CURRENT_DUMP["dumped_files"] = 0
    CURRENT_DUMP["failed_files"] = 0
    CURRENT_DUMP["start_time"] = time.time()
    CURRENT_DUMP["cancel_requested"] = False
    CURRENT_DUMP["status_msg_id"] = query.message.id
    CURRENT_DUMP["status_chat_id"] = query.message.chat.id
    CURRENT_DUMP["admin_id"] = query.from_user.id

    initial_text = (
        "🚀 <b><u>Database Dump Started!</u></b>\n\n"
        f"📢 <b>Target Channel:</b> <code>{target_channel_title}</code> (<code>{target_channel_id}</code>)\n"
        f"📊 <b>Total Files:</b> <code>{total_files:,}</code>\n"
        "✅ <b>Uploaded:</b> <code>0</code>\n"
        "❌ <b>Failed / Skipped:</b> <code>0</code>\n"
        f"⏳ <b>Remaining:</b> <code>{total_files:,}</code>\n"
        f"📈 <b>Progress:</b> <code>0.0%</code> [{create_progress_bar(0, total_files)}]\n"
        "⏱ <b>Elapsed Time:</b> <code>00m 00s</code>\n\n"
        "⚡ <i>Files are sorted by Name (A-Z). Upload speed boosted with flood-safe streaming!</i>"
    )
    buttons = [
        [
            InlineKeyboardButton("🔄 Refresh Status", callback_data="dump_refresh_status"),
            InlineKeyboardButton("🛑 Stop Dump", callback_data="dump_stop_confirm")
        ]
    ]
    await safe_edit_or_replace(client, query.message, initial_text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer("🚀 Dump process started!", show_alert=False)

    # Launch background dump worker
    task = asyncio.create_task(run_database_dump_worker(client))
    CURRENT_DUMP["task"] = task


# =========================================================================
# Background Worker: Stream all DB files sorted by Name (A-Z)
# =========================================================================

async def run_database_dump_worker(client: Client):
    logger.info(f"Starting Database Dump to channel {CURRENT_DUMP['target_channel_id']} (Sorted by Name A-Z)")
    target_channel_id = CURRENT_DUMP["target_channel_id"]
    target_channel_title = CURRENT_DUMP["target_channel_title"]
    status_chat_id = CURRENT_DUMP["status_chat_id"]
    status_msg_id = CURRENT_DUMP["status_msg_id"]
    total = CURRENT_DUMP["total_files"]
    
    last_ui_update = time.time()
    custom_dump_caption = await db.get_dump_caption()
    
    async def update_live_status():
        nonlocal last_ui_update
        if time.time() - last_ui_update < 4:
            return
        last_ui_update = time.time()
        dumped = CURRENT_DUMP["dumped_files"]
        failed = CURRENT_DUMP["failed_files"]
        elapsed = time.time() - CURRENT_DUMP["start_time"]
        remaining = max(0, total - dumped - failed)
        pct = (dumped + failed) / total * 100 if total > 0 else 0
        pbar = create_progress_bar(dumped + failed, total)
        
        # Calculate ETA
        processed = dumped + failed
        if processed > 0 and elapsed > 0:
            speed = processed / elapsed
            eta_seconds = remaining / speed if speed > 0 else 0
            eta_str = format_duration(eta_seconds)
        else:
            eta_str = "Calculating..."

        text = (
            "🚀 <b><u>Database Dump In Progress</u></b>\n\n"
            f"📢 <b>Target Channel:</b> <code>{target_channel_title}</code>\n"
            f"📊 <b>Total Files:</b> <code>{total:,}</code>\n"
            f"✅ <b>Uploaded:</b> <code>{dumped:,}</code>\n"
            f"❌ <b>Failed / Skipped:</b> <code>{failed:,}</code>\n"
            f"⏳ <b>Remaining:</b> <code>{remaining:,}</code>\n"
            f"📈 <b>Progress:</b> <code>{pct:.1f}%</code> [{pbar}]\n"
            f"⏱ <b>Elapsed Time:</b> <code>{format_duration(elapsed)}</code>\n"
            f"⌛ <b>Estimated Time Left (ETA):</b> <code>{eta_str}</code>\n\n"
            "⚡ <i>Uploading files sorted by Name (A-Z) with fast 3x speed!</i>"
        )
        buttons = [
            [
                InlineKeyboardButton("🔄 Refresh Status", callback_data="dump_refresh_status"),
                InlineKeyboardButton("🛑 Stop Dump", callback_data="dump_stop_confirm")
            ]
        ]
        try:
            await client.edit_message_text(
                chat_id=status_chat_id,
                message_id=status_msg_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except (MessageNotModified, Exception):
            pass

    async def dump_cursor(cursor):
        async for doc in cursor:
            if CURRENT_DUMP["cancel_requested"]:
                return False
            
            # Extract fields from raw MongoDB dictionary or object
            if isinstance(doc, dict):
                file_id = doc.get("file_id") or doc.get("_id")
                raw_name = doc.get("file_name") or "File"
                raw_size = doc.get("file_size", 0)
                raw_caption = doc.get("caption")
                cover = doc.get("cover")
            else:
                file_id = getattr(doc, "file_id", None) or getattr(doc, "id", None)
                raw_name = getattr(doc, "file_name", "File")
                raw_size = getattr(doc, "file_size", 0)
                raw_caption = getattr(doc, "caption", None)
                cover = getattr(doc, "cover", None)
                
            if not file_id:
                CURRENT_DUMP["failed_files"] += 1
                continue
                
            file_id_str = str(file_id)
            file_name = clean_filename(str(raw_name))
            try:
                file_size = get_size(int(raw_size))
            except Exception:
                file_size = "N/A"
            
            # Format Caption: Custom Dump Caption > Custom Bot Caption > Raw/Default
            if custom_dump_caption:
                try:
                    caption = custom_dump_caption.format(
                        file_name=file_name,
                        file_size=file_size,
                        file_caption=raw_caption or file_name
                    )
                except Exception:
                    caption = f"📁 <b>{file_name}</b> [{file_size}]"
            elif raw_caption:
                caption = raw_caption
            elif CUSTOM_FILE_CAPTION:
                try:
                    caption = CUSTOM_FILE_CAPTION.format(
                        file_name=file_name,
                        file_size=file_size,
                        file_caption=file_name
                    )
                except Exception:
                    caption = file_name
            else:
                caption = f"📁 <b>{file_name}</b> [{file_size}]"

            # Fast sending with instant FloodWait retry
            sent = False
            for attempt in range(3):
                if CURRENT_DUMP["cancel_requested"]:
                    return False
                try:
                    await client.send_cached_media(
                        chat_id=target_channel_id,
                        file_id=file_id_str,
                        caption=caption,
                        cover=cover
                    )
                    sent = True
                    CURRENT_DUMP["dumped_files"] += 1
                    break
                except FloodWait as e:
                    logger.warning(f"FloodWait during dump: sleeping for {e.value + 1}s")
                    await asyncio.sleep(e.value + 1)
                except Exception as e:
                    logger.error(f"Error dumping file {file_name}: {e}")
                    # If failed with cover on first attempt, retry without cover
                    if cover and attempt == 0:
                        cover = None
                        continue
                    await asyncio.sleep(0.3)
                    break

            if not sent and not CURRENT_DUMP["cancel_requested"]:
                CURRENT_DUMP["failed_files"] += 1

            # Update live UI
            await update_live_status()

            # Fast delay (0.2s) between uploads for high speed + telegram safety
            await asyncio.sleep(0.2)

        return True

    sort_mode = await db.get_dump_sort_mode()

    async def get_safely_sorted_cursor(coll):
        projection = {"_id": 1, "file_id": 1, "file_name": 1, "file_size": 1, "caption": 1, "cover": 1}
        
        # 1. Latest Added First (Natural reverse order - most recent movies first)
        if sort_mode == "latest":
            return coll.find({}, projection).sort("$natural", -1)

        # 2. Name Wise (A to Z)
        # Create index on file_name in background so sorting requires zero memory and runs at lightning speed
        try:
            await coll.create_index([("file_name", 1)], background=True)
        except Exception as ie:
            logger.warning(f"Index creation note: {ie}")

        # Query with allow_disk_use=True to prevent 32MB memory limit error
        try:
            cur = coll.find({}, projection, allow_disk_use=True).sort("file_name", 1)
            return cur
        except TypeError:
            pass
        except Exception as e:
            logger.warning(f"find with allow_disk_use param failed: {e}")

        try:
            cur = coll.find({}, projection).sort("file_name", 1)
            if hasattr(cur, "allow_disk_use"):
                cur.allow_disk_use(True)
            return cur
        except Exception as e:
            logger.warning(f"allow_disk_use method failed: {e}")
            return coll.find({}, projection)

    worker_error = None
    try:
        # 1. Primary DB collection dump sorted Alphabetically by file_name using raw Motor collection
        primary_coll = getattr(Media, "collection", None)
        if primary_coll is None:
            primary_coll = media_db[COLLECTION_NAME]
            
        primary_cursor = await get_safely_sorted_cursor(primary_coll)
        completed_primary = await dump_cursor(primary_cursor)

        # 2. Secondary DB collection dump (if MULTIPLE_DB enabled)
        if completed_primary and MULTIPLE_DB and not CURRENT_DUMP["cancel_requested"]:
            secondary_coll = getattr(Media2, "collection", None)
            if secondary_coll is None and media_db2 is not None:
                secondary_coll = media_db2[COLLECTION_NAME]
            if secondary_coll is not None:
                secondary_cursor = await get_safely_sorted_cursor(secondary_coll)
                await dump_cursor(secondary_cursor)

    except Exception as e:
        logger.exception(f"Unexpected error in dump worker: {e}")
        worker_error = str(e)

    # =========================================================================
    # Post Dump Handling: Cancellation, Error or Full Completion
    # =========================================================================
    elapsed_total = time.time() - CURRENT_DUMP["start_time"]
    dumped = CURRENT_DUMP["dumped_files"]
    failed = CURRENT_DUMP["failed_files"]
    
    if CURRENT_DUMP["cancel_requested"]:
        stop_text = (
            "🛑 <b><u>Database Dump Stopped!</u></b>\n\n"
            "The dump process was stopped by the administrator.\n\n"
            f"📢 <b>Target Channel:</b> <code>{target_channel_title}</code>\n"
            f"📊 <b>Total Uploaded:</b> <code>{dumped:,} / {total:,}</code>\n"
            f"❌ <b>Failed / Skipped:</b> <code>{failed:,}</code>\n"
            f"⏱ <b>Time Elapsed:</b> <code>{format_duration(elapsed_total)}</code>\n\n"
            "<i>Target channel session has been closed.</i>"
        )
        buttons = [
            [InlineKeyboardButton("📦 Dump Settings", callback_data="dump_settings_panel")],
            [InlineKeyboardButton("⚙️ Admin Menu", callback_data="admin_settings")]
        ]
        try:
            await client.edit_message_text(
                chat_id=status_chat_id,
                message_id=status_msg_id,
                text=stop_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass
    elif worker_error and dumped == 0:
        error_text = (
            "⚠️ <b><u>Database Dump Error!</u></b>\n\n"
            f"An error occurred while reading files from database:\n"
            f"<code>{worker_error}</code>\n\n"
            f"📢 <b>Target Channel:</b> <code>{target_channel_title}</code>\n"
            f"⏱ <b>Elapsed:</b> <code>{format_duration(elapsed_total)}</code>"
        )
        buttons = [
            [InlineKeyboardButton("🔄 Try Again", callback_data="dump_start_prompt")],
            [InlineKeyboardButton("📦 Dump Menu", callback_data="dump_settings_panel")]
        ]
        try:
            await client.edit_message_text(
                chat_id=status_chat_id,
                message_id=status_msg_id,
                text=error_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass
    else:
        # Full Completion Celebratory Message
        complete_text = (
            "🎉 <b><u>Database Dump Completed Successfully!</u></b>\n\n"
            "All stored movies and files from MongoDB have been dumped to your channel in alphabetical sequence.\n\n"
            f"📢 <b>Target Channel:</b> <code>{target_channel_title}</code> (<code>{target_channel_id}</code>)\n"
            f"📂 <b>Total Files in DB:</b> <code>{total:,}</code>\n"
            f"✅ <b>Successfully Dumped:</b> <code>{dumped:,}</code>\n"
            f"❌ <b>Failed / Skipped:</b> <code>{failed:,}</code>\n"
            f"⏱ <b>Total Time Taken:</b> <code>{format_duration(elapsed_total)}</code>\n\n"
            "✨ <b>Note:</b> <i>The target channel has been reset from memory. To dump again in the future, simply configure a channel from the menu!</i>"
        )
        buttons = [
            [
                InlineKeyboardButton("📦 Dump Menu", callback_data="dump_settings_panel"),
                InlineKeyboardButton("⚙️ Admin Menu", callback_data="admin_settings")
            ],
            [
                InlineKeyboardButton("⇋ Home ⇋", callback_data="start")
            ]
        ]
        try:
            await client.edit_message_text(
                chat_id=status_chat_id,
                message_id=status_msg_id,
                text=complete_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass

    # Reset all dump states and channel so the bot forgets the channel until next run
    CURRENT_DUMP["is_running"] = False
    CURRENT_DUMP["target_channel_id"] = None
    CURRENT_DUMP["target_channel_title"] = None
    CURRENT_DUMP["cancel_requested"] = False
    CURRENT_DUMP["task"] = None
    logger.info("Database Dump Worker completed and channel reset.")


# =========================================================================
# Step 4: Refresh Status & Stop Dump Handlers
# =========================================================================

@Client.on_callback_query(filters.regex(r"^dump_refresh_status$"))
async def dump_refresh_status_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await show_dump_panel(client, query.message)
    await query.answer("🔄 Status Refreshed!")


@Client.on_callback_query(filters.regex(r"^dump_stop_confirm$"))
async def dump_stop_confirm_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    if not CURRENT_DUMP["is_running"]:
        return await query.answer("ℹ️ No active dump process is running.", show_alert=True)
    
    confirm_text = (
        "⚠️ <b><u>Stop Dump Process?</u></b>\n\n"
        "Are you sure you want to halt the database dump in progress?\n"
        f"Dumped so far: <code>{CURRENT_DUMP['dumped_files']:,} / {CURRENT_DUMP['total_files']:,}</code>"
    )
    buttons = [
        [
            InlineKeyboardButton("🛑 Yes, Stop Now", callback_data="dump_stop_execute"),
            InlineKeyboardButton("« Keep Running", callback_data="dump_refresh_status")
        ]
    ]
    await safe_edit_or_replace(client, query.message, confirm_text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^dump_stop_execute$"))
async def dump_stop_execute_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    if not CURRENT_DUMP["is_running"]:
        return await query.answer("ℹ️ No active dump is running.", show_alert=True)
    
    CURRENT_DUMP["cancel_requested"] = True
    await query.answer("🛑 Stopping dump process...", show_alert=True)


@Client.on_message(filters.command(["stop_dump", "stopdump"]) & filters.private)
async def stop_dump_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    if not CURRENT_DUMP["is_running"]:
        return await message.reply_text("ℹ️ <b>No active dump process is running.</b>")
    
    CURRENT_DUMP["cancel_requested"] = True
    await message.reply_text("🛑 <b>Stopping Database Dump...</b> Please wait a moment for the worker to exit gracefully.")
