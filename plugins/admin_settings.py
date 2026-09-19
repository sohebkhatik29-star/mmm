import re
import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)
from pyrogram.errors import (
    ChatAdminRequired,
    UserNotParticipant,
    ChannelInvalid,
    PeerIdInvalid,
    UsernameInvalid,
    UsernameNotModified
)
from database.users_chats_db import db
from info import ADMINS, LOG_CHANNEL
from utils import temp, get_all_fsub_channels_list

logger = logging.getLogger(__name__)

# State storage for admin interactive inputs
AWAITING_FSUB_CHANNEL = {}

def is_admin(user_id: int) -> bool:
    try:
        uid = int(user_id)
        return uid in ADMINS or str(uid) in [str(a) for a in ADMINS]
    except Exception:
        return False


def get_admin_panel_markup() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("📢 Force Subscribe (FSUB)", callback_data="fsub_panel"),
            InlineKeyboardButton("📊 Bot Statistics", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("➕ Add FSUB Channel", callback_data="fsub_add"),
            InlineKeyboardButton("➖ Remove FSUB Channel", callback_data="fsub_remove_menu")
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
    
    AWAITING_FSUB_CHANNEL.pop(message.from_user.id, None)
    
    text = (
        "⚙️ <b><u>Admin Control Panel</u></b>\n\n"
        f"👋 Welcome <b>{message.from_user.mention}</b>!\n\n"
        "Here you can manage Bot Settings, Multi-Channel Force Subscribe, and view real-time statistics."
    )
    await message.reply_text(text, reply_markup=get_admin_panel_markup())


@Client.on_callback_query(filters.regex(r"^admin_settings$"))
async def admin_settings_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied! Only bot administrators can access this menu.", show_alert=True)
    
    AWAITING_FSUB_CHANNEL.pop(query.from_user.id, None)
    
    text = (
        "⚙️ <b><u>Admin Control Panel</u></b>\n\n"
        f"👋 Welcome <b>{query.from_user.mention}</b>!\n\n"
        "Here you can manage Bot Settings, Multi-Channel Force Subscribe, and view real-time statistics."
    )
    try:
        await query.message.edit_text(text, reply_markup=get_admin_panel_markup())
    except Exception:
        await query.message.reply_text(text, reply_markup=get_admin_panel_markup())
    await query.answer()


# =========================================================================
# Force Subscribe Panel
# =========================================================================

@Client.on_message(filters.command(["fsub", "forcesub", "fsub_list"]) & filters.private)
async def fsub_panel_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    AWAITING_FSUB_CHANNEL.pop(message.from_user.id, None)
    channels = await db.get_all_fsub_channels()
    
    text = (
        "📢 <b><u>Force Subscribe (FSUB) Management</u></b>\n\n"
        "Users will be required to join all active Force Sub channels before accessing files or searching.\n\n"
    )
    
    if channels:
        text += f"<b>📌 Active Channels ({len(channels)}):</b>\n"
        for idx, ch in enumerate(channels, 1):
            title = ch.get("title", "Unnamed Channel")
            ch_id = ch.get("channel_id")
            link = ch.get("invite_link", "")
            if link:
                text += f"{idx}. <b>{title}</b> (<code>{ch_id}</code>) - <a href='{link}'>Join Link</a>\n"
            else:
                text += f"{idx}. <b>{title}</b> (<code>{ch_id}</code>)\n"
    else:
        text += "ℹ️ <i>No dynamic Force Sub channels configured yet. Click '➕ Add Channel' below!</i>\n"
    
    buttons = [
        [
            InlineKeyboardButton("➕ Add Channel", callback_data="fsub_add"),
            InlineKeyboardButton("➖ Remove Channel", callback_data="fsub_remove_menu")
        ],
        [
            InlineKeyboardButton("🗑️ Clear All Channels", callback_data="fsub_clear_all"),
            InlineKeyboardButton("🔄 Refresh List", callback_data="fsub_panel")
        ],
        [
            InlineKeyboardButton("« Back to Admin", callback_data="admin_settings"),
            InlineKeyboardButton("⇋ Home ⇋", callback_data="start")
        ]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"^fsub_panel$"))
async def fsub_panel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    AWAITING_FSUB_CHANNEL.pop(query.from_user.id, None)
    channels = await db.get_all_fsub_channels()
    
    text = (
        "📢 <b><u>Force Subscribe (FSUB) Management</u></b>\n\n"
        "Users will be required to join all active Force Sub channels before accessing files or searching.\n\n"
    )
    
    if channels:
        text += f"<b>📌 Active Channels ({len(channels)}):</b>\n"
        for idx, ch in enumerate(channels, 1):
            title = ch.get("title", "Unnamed Channel")
            ch_id = ch.get("channel_id")
            link = ch.get("invite_link", "")
            if link:
                text += f"{idx}. <b>{title}</b> (<code>{ch_id}</code>) - <a href='{link}'>Join Link</a>\n"
            else:
                text += f"{idx}. <b>{title}</b> (<code>{ch_id}</code>)\n"
    else:
        text += "ℹ️ <i>No dynamic Force Sub channels configured yet. Click '➕ Add Channel' below!</i>\n"
    
    buttons = [
        [
            InlineKeyboardButton("➕ Add Channel", callback_data="fsub_add"),
            InlineKeyboardButton("➖ Remove Channel", callback_data="fsub_remove_menu")
        ],
        [
            InlineKeyboardButton("🗑️ Clear All Channels", callback_data="fsub_clear_all"),
            InlineKeyboardButton("🔄 Refresh List", callback_data="fsub_panel")
        ],
        [
            InlineKeyboardButton("« Back to Admin", callback_data="admin_settings"),
            InlineKeyboardButton("⇋ Home ⇋", callback_data="start")
        ]
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    except Exception:
        pass
    await query.answer()


# =========================================================================
# Add Force Subscribe Channel Flow
# =========================================================================

@Client.on_message(filters.command(["add_fsub", "addfsub"]) & filters.private)
async def add_fsub_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    AWAITING_FSUB_CHANNEL[message.from_user.id] = True
    text = (
        "➕ <b><u>Add Force Subscribe Channel</u></b>\n\n"
        "👉 <b>Forward any message from your target channel</b> to this bot.\n\n"
        "<i>(Alternatively, send the Channel ID like <code>-100xxxxxxx</code>, @username, or Invite Link)</i>\n\n"
        "⚠️ <b>Important Checklist:</b>\n"
        "1. Bot <b>MUST be an ADMIN</b> in the channel.\n"
        "2. Bot must have permission to <b>Invite Users via Link</b> or <b>Add Members</b>.\n\n"
        "Send /cancel to cancel."
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="fsub_panel")]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^fsub_add$"))
async def fsub_add_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    AWAITING_FSUB_CHANNEL[query.from_user.id] = True
    text = (
        "➕ <b><u>Add Force Subscribe Channel</u></b>\n\n"
        "👉 <b>Forward any message from your target channel</b> to this bot.\n\n"
        "<i>(Alternatively, send the Channel ID like <code>-100xxxxxxx</code>, @username, or Invite Link)</i>\n\n"
        "⚠️ <b>Important Checklist:</b>\n"
        "1. Bot <b>MUST be an ADMIN</b> in the channel.\n"
        "2. Bot must have permission to <b>Invite Users via Link</b> or <b>Add Members</b>.\n\n"
        "Send /cancel to cancel."
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="fsub_panel")]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_message(filters.private & ~filters.bot & filters.incoming, group=1)
async def handle_fsub_channel_input(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    if not AWAITING_FSUB_CHANNEL.get(user_id):
        return

    # Check for cancellation
    if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
        AWAITING_FSUB_CHANNEL.pop(user_id, None)
        buttons = [[InlineKeyboardButton("« Back to FSUB Panel", callback_data="fsub_panel")]]
        return await message.reply_text("🚫 <b>Operation Cancelled.</b>", reply_markup=InlineKeyboardMarkup(buttons))

    status_msg = await message.reply_text("🔍 <b>Verifying Channel & Permissions...</b> Please wait...")

    target_chat = None
    target_chat_identifier = None

    # 1. Check if forwarded from a channel
    if message.forward_from_chat:
        target_chat_identifier = message.forward_from_chat.id
    elif message.text:
        raw_text = message.text.strip()
        # Check if ID
        if re.match(r"^-100\d+$", raw_text) or re.match(r"^-\d+$", raw_text):
            target_chat_identifier = int(raw_text)
        elif raw_text.startswith("@"):
            target_chat_identifier = raw_text
        elif "t.me/" in raw_text:
            # Extract username or join link from URL
            clean_url = raw_text.split("?")[0].rstrip("/")
            if "/+" in clean_url or "/joinchat/" in clean_url:
                target_chat_identifier = clean_url
            else:
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
        return await status_msg.edit_text(
            "❌ <b>Invalid Input!</b>\n\nPlease forward a message from the channel or send a valid Channel ID / @username.\nSend /cancel to abort."
        )

    # 2. Fetch Chat details from Telegram
    try:
        target_chat = await client.get_chat(target_chat_identifier)
    except Exception as e:
        logger.error(f"Failed to fetch chat {target_chat_identifier}: {e}")
        return await status_msg.edit_text(
            f"❌ <b>Could not find or access this channel!</b>\n\n"
            f"<b>Error:</b> <code>{e}</code>\n\n"
            f"👉 <b>Make sure:</b>\n"
            f"1. You have already added the bot as an <b>ADMIN</b> in that channel.\n"
            f"2. The ID or Username is valid.\n\n"
            f"Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="fsub_panel")]])
        )

    if not target_chat:
        return await status_msg.edit_text("❌ Could not retrieve chat details. Please try again or send /cancel.")

    # 3. Check Bot Admin Status in the Chat
    try:
        bot_member = await client.get_chat_member(target_chat.id, "me")
        if bot_member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return await status_msg.edit_text(
                f"❌ <b>Bot is NOT an Admin in {target_chat.title}!</b>\n\n"
                f"👉 Please open channel settings, add this bot as an <b>ADMINISTRATOR</b> with <b>'Invite Users via Link'</b> permissions, and try forwarding again.\n\n"
                f"Send /cancel to abort."
            )
    except Exception as e:
        logger.error(f"Error checking bot admin status in {target_chat.id}: {e}")
        return await status_msg.edit_text(
            f"❌ <b>Failed to verify admin rights:</b> <code>{e}</code>\n\n"
            f"Make sure the bot is an Administrator in <b>{target_chat.title}</b>!"
        )

    # 4. Generate or Retrieve Invite Link
    invite_link = None
    try:
        invite = await client.create_chat_invite_link(target_chat.id)
        invite_link = invite.invite_link
    except Exception as e:
        logger.warning(f"Could not create invite link for {target_chat.id}: {e}")
        invite_link = target_chat.invite_link or (f"https://t.me/{target_chat.username}" if target_chat.username else "")

    if not invite_link:
        return await status_msg.edit_text(
            f"❌ <b>Failed to create invite link!</b>\n\n"
            f"Please ensure the bot has <b>'Invite Users via Link'</b> admin permission in <b>{target_chat.title}</b>."
        )

    # 5. Save Channel in Database
    try:
        await db.add_fsub_channel(
            channel_id=target_chat.id,
            title=target_chat.title,
            invite_link=invite_link
        )
        # Clear temporary cache
        temp.TEMP_INVITE_LINKS.clear()
        AWAITING_FSUB_CHANNEL.pop(user_id, None)

        success_text = (
            "✅ <b><u>Force Subscribe Channel Added Successfully!</u></b>\n\n"
            f"📢 <b>Channel Name:</b> {target_chat.title}\n"
            f"🆔 <b>Channel ID:</b> <code>{target_chat.id}</code>\n"
            f"🔗 <b>Invite Link:</b> <a href='{invite_link}'>Click to Open</a>\n\n"
            "✨ <i>All bot users will now be required to join this channel before getting movie files!</i>"
        )
        buttons = [
            [
                InlineKeyboardButton("➕ Add Another Channel", callback_data="fsub_add"),
                InlineKeyboardButton("📢 FSUB Panel", callback_data="fsub_panel")
            ],
            [
                InlineKeyboardButton("« Admin Panel", callback_data="admin_settings"),
                InlineKeyboardButton("⇋ Home ⇋", callback_data="start")
            ]
        ]
        await status_msg.edit_text(success_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

    except Exception as e:
        logger.exception("Error saving fsub channel: %s", e)
        await status_msg.edit_text(f"❌ <b>Database Error:</b> <code>{e}</code>")


# =========================================================================
# Remove Force Subscribe Channel Flow
# =========================================================================

@Client.on_message(filters.command(["del_fsub", "delfsub"]) & filters.private)
async def del_fsub_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    AWAITING_FSUB_CHANNEL.pop(message.from_user.id, None)
    channels = await db.get_all_fsub_channels()
    
    if not channels:
        return await message.reply_text(
            "ℹ️ <b>No dynamic Force Sub channels found to remove.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")]])
        )

    buttons = []
    for ch in channels:
        title = ch.get("title", "Channel")
        ch_id = ch.get("channel_id")
        buttons.append([
            InlineKeyboardButton(f"❌ {title} ({ch_id})", callback_data=f"fsub_del_{ch_id}")
        ])
    
    buttons.append([InlineKeyboardButton("🗑️ Clear All Channels", callback_data="fsub_clear_all")])
    buttons.append([InlineKeyboardButton("« Back to FSUB Panel", callback_data="fsub_panel")])
    
    await message.reply_text(
        "➖ <b><u>Remove Force Subscribe Channel</u></b>\n\n"
        "Click on any channel below to remove it from Force Subscribe:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_callback_query(filters.regex(r"^fsub_remove_menu$"))
async def fsub_remove_menu_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    AWAITING_FSUB_CHANNEL.pop(query.from_user.id, None)
    channels = await db.get_all_fsub_channels()
    
    if not channels:
        return await query.message.edit_text(
            "ℹ️ <b>No dynamic Force Sub channels found to remove.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")]])
        )

    buttons = []
    for ch in channels:
        title = ch.get("title", "Channel")
        ch_id = ch.get("channel_id")
        buttons.append([
            InlineKeyboardButton(f"❌ {title} ({ch_id})", callback_data=f"fsub_del_{ch_id}")
        ])
    
    buttons.append([InlineKeyboardButton("🗑️ Clear All Channels", callback_data="fsub_clear_all")])
    buttons.append([InlineKeyboardButton("« Back to FSUB Panel", callback_data="fsub_panel")])
    
    try:
        await query.message.edit_text(
            "➖ <b><u>Remove Force Subscribe Channel</u></b>\n\n"
            "Click on any channel below to remove it from Force Subscribe:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        pass
    await query.answer()


@Client.on_callback_query(filters.regex(r"^fsub_del_(-?\d+)$"))
async def fsub_del_single_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    channel_id = int(query.matches[0].group(1))
    success = await db.remove_fsub_channel(channel_id)
    temp.TEMP_INVITE_LINKS.clear()
    
    if success:
        await query.answer(f"✅ Channel ({channel_id}) removed from Force Sub!", show_alert=True)
    else:
        await query.answer(f"⚠️ Channel was not found or already removed.", show_alert=True)
    
    # Refresh remove menu
    channels = await db.get_all_fsub_channels()
    if not channels:
        return await query.message.edit_text(
            "✅ <b>All dynamic Force Sub channels have been removed!</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Channel", callback_data="fsub_add")],
                [InlineKeyboardButton("« Back to FSUB Panel", callback_data="fsub_panel")]
            ])
        )
    
    buttons = []
    for ch in channels:
        title = ch.get("title", "Channel")
        ch_id = ch.get("channel_id")
        buttons.append([
            InlineKeyboardButton(f"❌ {title} ({ch_id})", callback_data=f"fsub_del_{ch_id}")
        ])
    
    buttons.append([InlineKeyboardButton("🗑️ Clear All Channels", callback_data="fsub_clear_all")])
    buttons.append([InlineKeyboardButton("« Back to FSUB Panel", callback_data="fsub_panel")])
    
    try:
        await query.message.edit_text(
            "➖ <b><u>Remove Force Subscribe Channel</u></b>\n\n"
            "Click on any channel below to remove it from Force Subscribe:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^fsub_clear_all$"))
async def fsub_clear_all_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    buttons = [
        [
            InlineKeyboardButton("⚠️ Yes, Clear All", callback_data="fsub_confirm_clear"),
            InlineKeyboardButton("❌ Cancel", callback_data="fsub_panel")
        ]
    ]
    await query.message.edit_text(
        "⚠️ <b><u>Confirmation Required</u></b>\n\n"
        "Are you sure you want to <b>remove ALL dynamically added Force Subscribe channels</b>?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await query.answer()


@Client.on_callback_query(filters.regex(r"^fsub_confirm_clear$"))
async def fsub_confirm_clear_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    count = await db.clear_all_fsub_channels()
    temp.TEMP_INVITE_LINKS.clear()
    
    await query.answer(f"✅ Cleared {count} Force Sub channels!", show_alert=True)
    
    buttons = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="fsub_add")],
        [InlineKeyboardButton("« Back to FSUB Panel", callback_data="fsub_panel")]
    ]
    await query.message.edit_text(
        f"✅ <b>Successfully removed all ({count}) dynamic Force Subscribe channels!</b>",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


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
