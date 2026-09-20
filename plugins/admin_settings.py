import logging
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)
from database.users_chats_db import db
from info import ADMINS

logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    try:
        uid = int(user_id)
        return uid in ADMINS or str(uid) in [str(a) for a in ADMINS]
    except Exception:
        return False


def get_admin_panel_markup() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("📢 ꜰᴏʀᴄᴇ ꜱᴜʙꜱᴄʀɪʙᴇ (ꜰꜱᴜʙ)", callback_data="fsub_panel")
        ],
        [
            InlineKeyboardButton("📝 ꜰɪʟᴇ ᴄᴀᴘᴛɪᴏɴ (ᴄᴀᴘᴛᴀɪɴ)", callback_data="caption_panel")
        ],
        [
            InlineKeyboardButton("🖼️ ꜱᴛᴀʀᴛ ᴛᴇxᴛ & ᴘʜᴏᴛᴏ", callback_data="start_config_panel")
        ],
        [
            InlineKeyboardButton("📊 ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("⇋ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


# =========================================================================
# Admin Panel Main Callback & Command
# =========================================================================

@Client.on_message(filters.command(["admin", "adminpanel", "settings"]) & filters.private)
async def admin_panel_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> This command is restricted to Bot Administrators only.")
    
    text = (
        "⚙️ <b><u>Admin Control Panel</u></b>\n\n"
        f"👋 Welcome <b>{message.from_user.mention}</b>!\n\n"
        "Here you can manage Bot Settings, Multi-Channel Force Subscribe, and view real-time statistics.\n\n"
        "Select an option below:"
    )
    await message.reply_text(text, reply_markup=get_admin_panel_markup())


@Client.on_callback_query(filters.regex(r"^admin_settings$"))
async def admin_settings_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied! Only bot administrators can access this menu.", show_alert=True)
    
    text = (
        "⚙️ <b><u>Admin Control Panel</u></b>\n\n"
        f"👋 Welcome <b>{query.from_user.mention}</b>!\n\n"
        "Here you can manage Bot Settings, Multi-Channel Force Subscribe, and view real-time statistics.\n\n"
        "Select an option below:"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_admin_panel_markup())
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await client.send_message(chat_id=query.message.chat.id, text=text, reply_markup=get_admin_panel_markup())
    await query.answer()


# =========================================================================
# Admin Bot Statistics Callback
# =========================================================================

@Client.on_callback_query(filters.regex(r"^admin_stats$"))
async def admin_stats_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    try:
        total_users = await db.total_users_count()
        total_chats = await db.total_chat_count()
        fsub_channels = await db.get_all_fsub_channels()
        premium_count = await db.all_premium_users()
        
        text = (
            "📊 <b><u>Bot Real-time Statistics</u></b>\n\n"
            f"👤 <b>Total Users:</b> <code>{total_users:,}</code>\n"
            f"👥 <b>Total Groups/Chats:</b> <code>{total_chats:,}</code>\n"
            f"🎟️ <b>Active Premium Users:</b> <code>{premium_count:,}</code>\n"
            f"📢 <b>Active Dynamic FSUB Channels:</b> <code>{len(fsub_channels)}</code>\n"
        )
        
        buttons = [
            [InlineKeyboardButton("🔄 Refresh Stats", callback_data="admin_stats")],
            [
                InlineKeyboardButton("« Back to Admin", callback_data="admin_settings"),
                InlineKeyboardButton("⇋ Home ⇋", callback_data="start")
            ]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error fetching admin stats: {e}")
        await query.answer(f"Error: {e}", show_alert=True)
