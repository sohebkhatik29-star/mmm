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
from info import ADMINS, FSUB_PICS
from utils import temp

logger = logging.getLogger(__name__)

# Admin interactive state tracking: {user_id: "add_channel" | "set_photo" | "set_message"}
ADMIN_FSUB_STATE = {}

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
            InlineKeyboardButton("🖼️ Force Sub Photo", callback_data="fsub_photo_menu"),
            InlineKeyboardButton("📝 Force Sub Message", callback_data="fsub_message_menu")
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
    
    ADMIN_FSUB_STATE.pop(message.from_user.id, None)
    total_channels = len(await db.get_all_fsub_channels())
    has_custom_photo = bool(await db.get_fsub_photo())
    has_custom_msg = bool(await db.get_fsub_message())
    
    text = (
        "📢 <b><u>Force Subscribe (FSUB) Management</u></b>\n\n"
        f"📊 <b>Active Channels:</b> <code>{total_channels}</code>\n"
        f"🖼️ <b>Custom Photo:</b> {'✅ Active' if has_custom_photo else '⚙️ Default'}\n"
        f"📝 <b>Custom Message:</b> {'✅ Active' if has_custom_msg else '⚙️ Default'}\n\n"
        "Choose an option below to configure Force Subscribe:"
    )
    await message.reply_text(text, reply_markup=get_fsub_main_markup())


@Client.on_callback_query(filters.regex(r"^fsub_panel$"))
async def fsub_panel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    ADMIN_FSUB_STATE.pop(query.from_user.id, None)
    total_channels = len(await db.get_all_fsub_channels())
    has_custom_photo = bool(await db.get_fsub_photo())
    has_custom_msg = bool(await db.get_fsub_message())
    
    text = (
        "📢 <b><u>Force Subscribe (FSUB) Management</u></b>\n\n"
        f"📊 <b>Active Channels:</b> <code>{total_channels}</code>\n"
        f"🖼️ <b>Custom Photo:</b> {'✅ Active' if has_custom_photo else '⚙️ Default'}\n"
        f"📝 <b>Custom Message:</b> {'✅ Active' if has_custom_msg else '⚙️ Default'}\n\n"
        "Choose an option below to configure Force Subscribe:"
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
    
    ADMIN_FSUB_STATE[message.from_user.id] = "add_channel"
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
    
    ADMIN_FSUB_STATE[query.from_user.id] = "add_channel"
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


# =========================================================================
# 3. ➖ Remove Force Sub Channel
# =========================================================================

@Client.on_message(filters.command(["del_fsub", "delfsub"]) & filters.private)
async def del_fsub_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    ADMIN_FSUB_STATE.pop(message.from_user.id, None)
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
    
    ADMIN_FSUB_STATE.pop(query.from_user.id, None)
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


# =========================================================================
# 4. 🖼️ Force Sub Photo Settings
# =========================================================================

@Client.on_message(filters.command(["fsub_photo", "set_fsub_photo"]) & filters.private)
async def fsub_photo_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    ADMIN_FSUB_STATE.pop(message.from_user.id, None)
    custom_photo = await db.get_fsub_photo()
    
    if custom_photo:
        text = (
            "🖼️ <b><u>Force Subscribe Photo Settings</u></b>\n\n"
            "✅ <b>Status:</b> Custom Photo is <b>ACTIVE</b>\n\n"
            "Har user ko channel join karte time yehi photo dikhegi.\n"
            "Aap is photo ko change ya default par reset kar sakte hain."
        )
        buttons = [
            [
                InlineKeyboardButton("🔄 Change Photo", callback_data="fsub_set_photo"),
                InlineKeyboardButton("🗑️ Reset to Default", callback_data="fsub_del_photo")
            ],
            [
                InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")
            ]
        ]
    else:
        text = (
            "🖼️ <b><u>Force Subscribe Photo Settings</u></b>\n\n"
            "⚙️ <b>Status:</b> Using <b>DEFAULT PHOTO</b>\n\n"
            "Abhi bot standard random photos use kar raha hai.\n"
            "Custom photo lagane ke liye '➕ Set Custom Photo' par click karein."
        )
        buttons = [
            [
                InlineKeyboardButton("➕ Set Custom Photo", callback_data="fsub_set_photo")
            ],
            [
                InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")
            ]
        ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^fsub_photo_menu$"))
async def fsub_photo_menu_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    ADMIN_FSUB_STATE.pop(query.from_user.id, None)
    custom_photo = await db.get_fsub_photo()
    
    if custom_photo:
        text = (
            "🖼️ <b><u>Force Subscribe Photo Settings</u></b>\n\n"
            "✅ <b>Status:</b> Custom Photo is <b>ACTIVE</b>\n\n"
            "Har user ko channel join karte time yehi photo dikhegi.\n"
            "Aap is photo ko change ya default par reset kar sakte hain."
        )
        buttons = [
            [
                InlineKeyboardButton("🔄 Change Photo", callback_data="fsub_set_photo"),
                InlineKeyboardButton("🗑️ Reset to Default", callback_data="fsub_del_photo")
            ],
            [
                InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")
            ]
        ]
    else:
        text = (
            "🖼️ <b><u>Force Subscribe Photo Settings</u></b>\n\n"
            "⚙️ <b>Status:</b> Using <b>DEFAULT PHOTO</b>\n\n"
            "Abhi bot standard random photos use kar raha hai.\n"
            "Custom photo lagane ke liye '➕ Set Custom Photo' par click karein."
        )
        buttons = [
            [
                InlineKeyboardButton("➕ Set Custom Photo", callback_data="fsub_set_photo")
            ],
            [
                InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")
            ]
        ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^fsub_set_photo$"))
async def fsub_set_photo_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    ADMIN_FSUB_STATE[query.from_user.id] = "set_photo"
    text = (
        "🖼️ <b><u>Set Custom Force Subscribe Photo</u></b>\n\n"
        "👉 <b>Photo bhejein (Direct image send karein ya image URL bhejein):</b>\n\n"
        "• Aap koi photo yahan bhej sakte hain\n"
        "• Ya kisi direct image link (Telegraph / Catbox / Imgur) ko text me bhej sakte hain\n\n"
        "Send /cancel to cancel."
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="fsub_photo_menu")]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^fsub_del_photo$"))
async def fsub_del_photo_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await db.delete_fsub_photo()
    await query.answer("✅ Force Sub photo reset to default!", show_alert=True)
    
    text = (
        "🖼️ <b><u>Force Subscribe Photo Settings</u></b>\n\n"
        "⚙️ <b>Status:</b> Using <b>DEFAULT PHOTO</b>\n\n"
        "Photo successfully default par reset ho gayi hai."
    )
    buttons = [
        [InlineKeyboardButton("➕ Set Custom Photo", callback_data="fsub_set_photo")],
        [InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")]
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass


# =========================================================================
# 5. 📝 Force Sub Message Settings
# =========================================================================

@Client.on_message(filters.command(["fsub_msg", "set_fsub_msg"]) & filters.private)
async def fsub_msg_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    ADMIN_FSUB_STATE.pop(message.from_user.id, None)
    custom_msg = await db.get_fsub_message()
    
    if custom_msg:
        text = (
            "📝 <b><u>Force Subscribe Message Settings</u></b>\n\n"
            "✅ <b>Status:</b> Custom Message is <b>ACTIVE</b>\n\n"
            f"<b>Current Message:</b>\n<blockquote>{custom_msg}</blockquote>\n\n"
            "📌 <b>Available Variables:</b>\n"
            "• <code>{mention}</code> - User Mention\n"
            "• <code>{first_name}</code> - User First Name\n"
            "• <code>{username}</code> - User @username\n"
            "• <code>{id}</code> - User ID"
        )
        buttons = [
            [
                InlineKeyboardButton("🔄 Change Message", callback_data="fsub_set_msg"),
                InlineKeyboardButton("🗑️ Reset to Default", callback_data="fsub_del_msg_custom")
            ],
            [
                InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")
            ]
        ]
    else:
        text = (
            "📝 <b><u>Force Subscribe Message Settings</u></b>\n\n"
            "⚙️ <b>Status:</b> Using <b>DEFAULT MESSAGE</b>\n\n"
            "<b>Default Message:</b>\n<blockquote>👋 ʜᴇʟʟᴏ {mention}\n\n🛑 ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ.\n👉 ᴊᴏɪɴ ᴀʟʟ ᴛʜᴇ ʙᴇʟᴏᴡ ᴄʜᴀɴɴᴇʟs ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ.</blockquote>\n\n"
            "📌 <b>Available Variables:</b>\n"
            "• <code>{mention}</code> - User Mention\n"
            "• <code>{first_name}</code> - User First Name\n"
            "• <code>{username}</code> - User @username\n"
            "• <code>{id}</code> - User ID"
        )
        buttons = [
            [
                InlineKeyboardButton("➕ Set Custom Message", callback_data="fsub_set_msg")
            ],
            [
                InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")
            ]
        ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^fsub_message_menu$"))
async def fsub_message_menu_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    ADMIN_FSUB_STATE.pop(query.from_user.id, None)
    custom_msg = await db.get_fsub_message()
    
    if custom_msg:
        text = (
            "📝 <b><u>Force Subscribe Message Settings</u></b>\n\n"
            "✅ <b>Status:</b> Custom Message is <b>ACTIVE</b>\n\n"
            f"<b>Current Message:</b>\n<blockquote>{custom_msg}</blockquote>\n\n"
            "📌 <b>Available Variables:</b>\n"
            "• <code>{mention}</code> - User Mention\n"
            "• <code>{first_name}</code> - User First Name\n"
            "• <code>{username}</code> - User @username\n"
            "• <code>{id}</code> - User ID"
        )
        buttons = [
            [
                InlineKeyboardButton("🔄 Change Message", callback_data="fsub_set_msg"),
                InlineKeyboardButton("🗑️ Reset to Default", callback_data="fsub_del_msg_custom")
            ],
            [
                InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")
            ]
        ]
    else:
        text = (
            "📝 <b><u>Force Subscribe Message Settings</u></b>\n\n"
            "⚙️ <b>Status:</b> Using <b>DEFAULT MESSAGE</b>\n\n"
            "<b>Default Message:</b>\n<blockquote>👋 ʜᴇʟʟᴏ {mention}\n\n🛑 ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ.\n👉 ᴊᴏɪɴ ᴀʟʟ ᴛʜᴇ ʙᴇʟᴏᴡ ᴄʜᴀɴɴᴇʟs ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ.</blockquote>\n\n"
            "📌 <b>Available Variables:</b>\n"
            "• <code>{mention}</code> - User Mention\n"
            "• <code>{first_name}</code> - User First Name\n"
            "• <code>{username}</code> - User @username\n"
            "• <code>{id}</code> - User ID"
        )
        buttons = [
            [
                InlineKeyboardButton("➕ Set Custom Message", callback_data="fsub_set_msg")
            ],
            [
                InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")
            ]
        ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^fsub_set_msg$"))
async def fsub_set_msg_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    ADMIN_FSUB_STATE[query.from_user.id] = "set_message"
    text = (
        "📝 <b><u>Set Custom Force Subscribe Message</u></b>\n\n"
        "👉 <b>Apna naya message text yahan type karke bhejein.</b>\n\n"
        "📌 <b>Aap in variables ka use kar sakte hain:</b>\n"
        "• <code>{mention}</code> - User Mention link\n"
        "• <code>{first_name}</code> - User ka First Name\n"
        "• <code>{username}</code> - User ka @username\n"
        "• <code>{id}</code> - User ka Telegram ID\n\n"
        "<b>Example:</b>\n"
        "<code>Hey {mention}, kripya hamare official channels join karein tabhi aapko movie file milegi!</code>\n\n"
        "Send /cancel to cancel."
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="fsub_message_menu")]]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^fsub_del_msg_custom$"))
async def fsub_del_msg_custom_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await db.delete_fsub_message()
    await query.answer("✅ Force Sub message reset to default!", show_alert=True)
    
    text = (
        "📝 <b><u>Force Subscribe Message Settings</u></b>\n\n"
        "⚙️ <b>Status:</b> Using <b>DEFAULT MESSAGE</b>\n\n"
        "Message successfully default par reset ho gaya hai."
    )
    buttons = [
        [InlineKeyboardButton("➕ Set Custom Message", callback_data="fsub_set_msg")],
        [InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")]
    ]
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass


# =========================================================================
# Unified Input Handler for Admin FSUB actions (Group 2)
# =========================================================================

@Client.on_message(filters.private & ~filters.bot & filters.incoming, group=2)
async def handle_fsub_admin_inputs(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    state = ADMIN_FSUB_STATE.get(user_id)
    if not state:
        return

    # Check for cancel
    if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
        ADMIN_FSUB_STATE.pop(user_id, None)
        buttons = [[InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")]]
        return await message.reply_text("🚫 <b>Operation Cancelled.</b>", reply_markup=InlineKeyboardMarkup(buttons))

    # -----------------------------------------------------------------
    # State 1: Setting Custom Photo
    # -----------------------------------------------------------------
    if state == "set_photo":
        photo_val = None
        if message.photo:
            photo_val = message.photo.file_id
        elif message.text:
            text_str = message.text.strip()
            if text_str.startswith("http://") or text_str.startswith("https://"):
                photo_val = text_str
            else:
                return await message.reply_text(
                    "❌ <b>Invalid Photo Input!</b>\n\nKripya direct image bhejein ya valid image URL (http/https) bhejein.\nSend /cancel to cancel."
                )
        elif message.reply_to_message and message.reply_to_message.photo:
            photo_val = message.reply_to_message.photo.file_id

        if not photo_val:
            return await message.reply_text(
                "❌ <b>No Photo Detected!</b>\n\nKripya image send karein ya URL bhejein.\nSend /cancel to cancel."
            )

        try:
            await db.set_fsub_photo(photo_val)
            ADMIN_FSUB_STATE.pop(user_id, None)

            success_text = (
                "✅ <b><u>Force Subscribe Photo Set Successfully!</u></b>\n\n"
                "Ab jab bhi koi user channel join karne aayega, usko ye custom photo dikhegi."
            )
            buttons = [
                [InlineKeyboardButton("🖼️ View Photo Settings", callback_data="fsub_photo_menu")],
                [InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")]
            ]
            return await message.reply_text(success_text, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            logger.exception("Error saving custom photo: %s", e)
            return await message.reply_text(f"❌ <b>Error:</b> <code>{e}</code>")

    # -----------------------------------------------------------------
    # State 2: Setting Custom Message
    # -----------------------------------------------------------------
    elif state == "set_message":
        if not message.text:
            return await message.reply_text(
                "❌ <b>Invalid Input!</b>\n\nKripya text message type karke bhejein.\nSend /cancel to cancel."
            )

        new_msg = message.text.html if hasattr(message.text, 'html') else message.text
        try:
            await db.set_fsub_message(new_msg)
            ADMIN_FSUB_STATE.pop(user_id, None)

            success_text = (
                "✅ <b><u>Force Subscribe Message Saved Successfully!</u></b>\n\n"
                f"<b>Saved Preview:</b>\n<blockquote>{new_msg}</blockquote>\n\n"
                "Ab users ko channel join karne ke prompt me yehi custom message dikhega."
            )
            buttons = [
                [InlineKeyboardButton("📝 View Message Settings", callback_data="fsub_message_menu")],
                [InlineKeyboardButton("« Back to FSUB", callback_data="fsub_panel")]
            ]
            return await message.reply_text(success_text, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            logger.exception("Error saving custom message: %s", e)
            return await message.reply_text(f"❌ <b>Error:</b> <code>{e}</code>")

    # -----------------------------------------------------------------
    # State 3: Adding Channel
    # -----------------------------------------------------------------
    elif state == "add_channel":
        status_msg = await message.reply_text("🔍 <b>Verifying Channel & Admin Permissions...</b> Please wait...")
        target_chat_identifier = None

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

        try:
            await db.add_fsub_channel(
                channel_id=target_chat.id,
                title=target_chat.title,
                invite_link=invite_link
            )
            temp.TEMP_INVITE_LINKS.clear()
            ADMIN_FSUB_STATE.pop(user_id, None)

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
