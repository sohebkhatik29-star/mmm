import re
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)
from database.users_chats_db import db
from info import ADMINS
from utils import temp

logger = logging.getLogger(__name__)

# Admin awaiting state for adding fsub channel
AWAITING_FSUB_CHANNEL = {}

def is_admin(user_id: int) -> bool:
    try:
        uid = int(user_id)
        return uid in ADMINS or str(uid) in [str(a) for a in ADMINS]
    except Exception:
        return False


def get_fsub_main_markup() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("➕ Add Force Sub", callback_data="fsub_add"),
            InlineKeyboardButton("➖ Remove Force Sub", callback_data="fsub_remove_menu")
        ],
        [
            InlineKeyboardButton("👁️ See Force Sub", callback_data="fsub_see_list")
        ],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴀᴅᴍɪɴ", callback_data="admin_settings"),
            InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


# =========================================================================
# Force Subscribe Main Menu
# =========================================================================

@Client.on_message(filters.command(["fsub", "forcesub"]) & filters.private)
async def fsub_panel_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    AWAITING_FSUB_CHANNEL.pop(message.from_user.id, None)
    total_channels = len(await db.get_all_fsub_channels())
    
    text = (
        "📢 <b><u>Force Subscribe (FSUB) Management</u></b>\n\n"
        f"📊 <b>Total Active Channels:</b> <code>{total_channels}</code>\n\n"
        "Choose an action below to manage Force Subscribe:"
    )
    await message.reply_text(text, reply_markup=get_fsub_main_markup())


@Client.on_callback_query(filters.regex(r"^fsub_panel$"))
async def fsub_panel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    AWAITING_FSUB_CHANNEL.pop(query.from_user.id, None)
    total_channels = len(await db.get_all_fsub_channels())
    
    text = (
        "📢 <b><u>Force Subscribe (FSUB) Management</u></b>\n\n"
        f"📊 <b>Total Active Channels:</b> <code>{total_channels}</code>\n\n"
        "Choose an action below to manage Force Subscribe:"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_fsub_main_markup())
    except Exception:
        await query.message.reply_text(text, reply_markup=get_fsub_main_markup())
    await query.answer()


# =========================================================================
# 1. 👁️ See Force Sub (List Channels)
# =========================================================================

@Client.on_callback_query(filters.regex(r"^fsub_see_list$"))
async def fsub_see_list_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    channels = await db.get_all_fsub_channels()
    
    text = (
        "👁️ <b><u>Active Force Subscribe Channels</u></b>\n\n"
    )
    
    if channels:
        text += f"📊 <b>Total Channels:</b> <code>{len(channels)}</code>\n\n"
        for idx, ch in enumerate(channels, 1):
            title = ch.get("title", "Unnamed Channel")
            ch_id = ch.get("channel_id")
            link = ch.get("invite_link", "")
            if link:
                text += f"<b>{idx}. {title}</b>\n🆔 <code>{ch_id}</code> | 🔗 <a href='{link}'>Join Link</a>\n\n"
            else:
                text += f"<b>{idx}. {title}</b>\n🆔 <code>{ch_id}</code>\n\n"
    else:
        text += "ℹ️ <i>Abhi koi bhi Force Sub channel add nahi hai.\nNiche diye gaye '➕ Add Force Sub' button se add karein!</i>\n\n"
    
    buttons = [
        [
            InlineKeyboardButton("➕ Add Force Sub", callback_data="fsub_add"),
            InlineKeyboardButton("➖ Remove Force Sub", callback_data="fsub_remove_menu")
        ],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ғsᴜʙ", callback_data="fsub_panel"),
            InlineKeyboardButton("🔄 ʀᴇғʀᴇsʜ", callback_data="fsub_see_list")
        ]
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    except Exception:
        pass
    await query.answer()


# =========================================================================
# 2. ➕ Add Force Sub Channel
# =========================================================================

@Client.on_message(filters.command(["add_fsub", "addfsub"]) & filters.private)
async def add_fsub_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    AWAITING_FSUB_CHANNEL[message.from_user.id] = True
    text = (
        "➕ <b><u>Add Force Subscribe Channel</u></b>\n\n"
        "👉 <b>Channel me se koi bhi message yahan forward karein.</b>\n\n"
        "<i>(Ya channel ka ID jaise <code>-100xxxxxxx</code>, @username, ya Invite Link bhejein)</i>\n\n"
        "⚠️ <b>Important:</b>\n"
        "• Bot us channel me <b>ADMIN</b> hona jaruri hai.\n"
        "• Bot ke paas <b>'Invite Users via Link'</b> permission honi chahiye.\n\n"
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
        "👉 <b>Channel me se koi bhi message yahan forward karein.</b>\n\n"
        "<i>(Ya channel ka ID jaise <code>-100xxxxxxx</code>, @username, ya Invite Link bhejein)</i>\n\n"
        "⚠️ <b>Important:</b>\n"
        "• Bot us channel me <b>ADMIN</b> hona jaruri hai.\n"
        "• Bot ke paas <b>'Invite Users via Link'</b> permission honi chahiye.\n\n"
        "Send /cancel to cancel."
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="fsub_panel")]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_message(filters.private & ~filters.bot & filters.incoming, group=2)
async def handle_fsub_channel_input(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    if not AWAITING_FSUB_CHANNEL.get(user_id):
        return

    # Check for cancel
    if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
        AWAITING_FSUB_CHANNEL.pop(user_id, None)
        buttons = [[InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")]]
        return await message.reply_text("🚫 <b>Operation Cancelled.</b>", reply_markup=InlineKeyboardMarkup(buttons))

    status_msg = await message.reply_text("🔍 <b>Verifying Channel & Admin Permissions...</b> Please wait...")

    target_chat_identifier = None

    # 1. Check forwarded message
    if message.forward_from_chat:
        target_chat_identifier = message.forward_from_chat.id
    elif message.text:
        raw_text = message.text.strip()
        if re.match(r"^-100\d+$", raw_text) or re.match(r"^-\d+$", raw_text):
            target_chat_identifier = int(raw_text)
        elif raw_text.startswith("@"):
            target_chat_identifier = raw_text
        elif "t.me/" in raw_text:
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
            "❌ <b>Invalid Input!</b>\n\nKripya channel se koi message forward karein ya valid Channel ID / Username bhejein.\nSend /cancel to cancel."
        )

    # 2. Get chat info
    try:
        target_chat = await client.get_chat(target_chat_identifier)
    except Exception as e:
        logger.error(f"Failed to fetch chat {target_chat_identifier}: {e}")
        return await status_msg.edit_text(
            f"❌ <b>Channel Access Error!</b>\n\n"
            f"<b>Details:</b> <code>{e}</code>\n\n"
            f"👉 <b>Ensure:</b>\n"
            f"1. Bot us channel me <b>ADMIN</b> hona chahiye.\n"
            f"2. Channel link ya ID sahi ho.\n\n"
            f"Send /cancel to cancel.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="fsub_panel")]])
        )

    # 3. Verify Bot Admin Rights
    try:
        bot_member = await client.get_chat_member(target_chat.id, "me")
        if bot_member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return await status_msg.edit_text(
                f"❌ <b>Bot is NOT an Admin in {target_chat.title}!</b>\n\n"
                f"👉 Pehle bot ko us channel me <b>Admin</b> banayein, fir message forward karein.\n\n"
                f"Send /cancel to cancel."
            )
    except Exception as e:
        logger.error(f"Error checking bot admin status in {target_chat.id}: {e}")
        return await status_msg.edit_text(
            f"❌ <b>Admin check failed:</b> <code>{e}</code>\n\n"
            f"Make sure bot is an Administrator in <b>{target_chat.title}</b>!"
        )

    # 4. Create/fetch invite link
    invite_link = None
    try:
        invite = await client.create_chat_invite_link(target_chat.id)
        invite_link = invite.invite_link
    except Exception as e:
        logger.warning(f"Could not create invite link for {target_chat.id}: {e}")
        invite_link = target_chat.invite_link or (f"https://t.me/{target_chat.username}" if target_chat.username else "")

    if not invite_link:
        return await status_msg.edit_text(
            f"❌ <b>Invite Link Error!</b>\n\n"
            f"Bot ke paas <b>'Invite Users via Link'</b> admin permission check karein in <b>{target_chat.title}</b>."
        )

    # 5. Save in Database
    try:
        await db.add_fsub_channel(
            channel_id=target_chat.id,
            title=target_chat.title,
            invite_link=invite_link
        )
        temp.TEMP_INVITE_LINKS.clear()
        AWAITING_FSUB_CHANNEL.pop(user_id, None)

        success_text = (
            "✅ <b><u>Force Subscribe Channel Added Successfully!</u></b>\n\n"
            f"📢 <b>Channel:</b> {target_chat.title}\n"
            f"🆔 <b>Channel ID:</b> <code>{target_chat.id}</code>\n"
            f"🔗 <b>Invite Link:</b> <a href='{invite_link}'>Click to Open</a>\n\n"
            "✨ <i>Ab users ko ye channel join karna padega files lene ke liye!</i>"
        )
        buttons = [
            [
                InlineKeyboardButton("➕ Add More", callback_data="fsub_add"),
                InlineKeyboardButton("👁️ See Force Sub", callback_data="fsub_see_list")
            ],
            [
                InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel"),
                InlineKeyboardButton("« Admin Panel", callback_data="admin_settings")
            ]
        ]
        await status_msg.edit_text(success_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

    except Exception as e:
        logger.exception("Error saving fsub channel: %s", e)
        await status_msg.edit_text(f"❌ <b>Database Error:</b> <code>{e}</code>")


# =========================================================================
# 3. ➖ Remove Force Sub Channel
# =========================================================================

@Client.on_message(filters.command(["del_fsub", "delfsub"]) & filters.private)
async def del_fsub_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    AWAITING_FSUB_CHANNEL.pop(message.from_user.id, None)
    channels = await db.get_all_fsub_channels()
    
    if not channels:
        return await message.reply_text(
            "ℹ️ <b>Koi bhi Force Sub channel add nahi hai remove karne ke liye.</b>",
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
    buttons.append([InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")])
    
    await message.reply_text(
        "➖ <b><u>Remove Force Subscribe Channel</u></b>\n\n"
        "Jis channel ko remove karna hai, uske button par click karein:",
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
            "ℹ️ <b>Koi bhi Force Sub channel add nahi hai remove karne ke liye.</b>",
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
    buttons.append([InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")])
    
    try:
        await query.message.edit_text(
            "➖ <b><u>Remove Force Subscribe Channel</u></b>\n\n"
            "Jis channel ko remove karna hai, uske button par click karein:",
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
        await query.answer(f"✅ Channel ({channel_id}) removed successfully!", show_alert=True)
    else:
        await query.answer(f"⚠️ Channel was not found.", show_alert=True)
    
    channels = await db.get_all_fsub_channels()
    if not channels:
        return await query.message.edit_text(
            "✅ <b>Sabhi Force Sub channels remove ho chuke hain!</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Force Sub", callback_data="fsub_add")],
                [InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")]
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
    buttons.append([InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")])
    
    try:
        await query.message.edit_text(
            "➖ <b><u>Remove Force Subscribe Channel</u></b>\n\n"
            "Jis channel ko remove karna hai, uske button par click karein:",
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
            InlineKeyboardButton("❌ Cancel", callback_data="fsub_remove_menu")
        ]
    ]
    await query.message.edit_text(
        "⚠️ <b><u>Confirmation Required</u></b>\n\n"
        "Kya aap sach me <b>SAARE Force Subscribe channels remove</b> karna chahte hain?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await query.answer()


@Client.on_callback_query(filters.regex(r"^fsub_confirm_clear$"))
async def fsub_confirm_clear_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    count = await db.clear_all_fsub_channels()
    temp.TEMP_INVITE_LINKS.clear()
    
    await query.answer(f"✅ Cleared {count} channels!", show_alert=True)
    
    buttons = [
        [InlineKeyboardButton("➕ Add Force Sub", callback_data="fsub_add")],
        [InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")]
    ]
    await query.message.edit_text(
        f"✅ <b>Successfully removed all ({count}) Force Subscribe channels!</b>",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
