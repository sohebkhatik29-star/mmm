import logging
import random
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)
from database.users_chats_db import db
from info import ADMINS, PICS, PICS_URL
from Script import script
from utils import temp, get_start_display_details, get_random_mix_id

logger = logging.getLogger(__name__)

# State trackers for admin setup
AWAITING_START_MSG = {}   # {user_id: {"state": True, "prompt_msg_id": int}}
AWAITING_START_PHOTO = {} # {user_id: {"state": True, "prompt_msg_id": int}}

def is_admin(user_id: int) -> bool:
    try:
        uid = int(user_id)
        return uid in ADMINS or str(uid) in [str(a) for a in ADMINS]
    except Exception:
        return False


async def safe_edit_or_replace(client: Client, message: Message, text: str, reply_markup: InlineKeyboardMarkup = None, disable_web_page_preview: bool = True):
    """Edits current message safely or deletes old message and sends new one to prevent stacking."""
    try:
        await message.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
    except Exception:
        try:
            await message.delete()
        except Exception:
            pass
        await client.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )


async def get_start_config_main_markup() -> InlineKeyboardMarkup:
    has_custom_msg = bool(await db.get_start_message())
    has_custom_photo = bool(await db.get_start_photo())

    msg_status = "🟢 Custom" if has_custom_msg else "⚪ Default"
    photo_status = "🟢 Custom" if has_custom_photo else "⚪ Default"

    buttons = [
        [
            InlineKeyboardButton(f"💬 Start Message [{msg_status}]", callback_data="start_msg_menu")
        ],
        [
            InlineKeyboardButton(f"📸 Start Photo [{photo_status}]", callback_data="start_photo_menu")
        ],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴀᴅᴍɪɴ", callback_data="admin_settings"),
            InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


# =========================================================================
# 1. Main Start Config Hub
# =========================================================================

@Client.on_callback_query(filters.regex(r"^start_config_panel$"))
async def start_config_panel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ This panel is restricted to Bot Admins only.", show_alert=True)
    
    AWAITING_START_MSG.pop(query.from_user.id, None)
    AWAITING_START_PHOTO.pop(query.from_user.id, None)
    await query.answer()

    custom_msg = await db.get_start_message()
    custom_photo = await db.get_start_photo()

    msg_status_text = "🟢 <b>Custom Start Message Active</b>" if custom_msg else "⚪ <b>Default System Text Active</b>"
    photo_status_text = "🟢 <b>Custom Start Photo Active</b>" if custom_photo else "⚪ <b>Default Random System Photos Active</b>"

    text = (
        "✨ <b><u>Start Message & Photo Settings</u></b>\n\n"
        "Here you can customize the greeting message and photo displayed to users when they send <code>/start</code>.\n\n"
        f"• <b>Start Message:</b> {msg_status_text}\n"
        f"• <b>Start Photo:</b> {photo_status_text}\n\n"
        "👇 <i>Choose a setting below to view, change, or reset:</i>"
    )

    markup = await get_start_config_main_markup()
    await safe_edit_or_replace(client, query.message, text, reply_markup=markup)


# =========================================================================
# 2. Start Message Sub-Menu & Actions
# =========================================================================

@Client.on_callback_query(filters.regex(r"^start_msg_menu$"))
async def start_msg_menu_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    AWAITING_START_MSG.pop(query.from_user.id, None)
    await query.answer()

    custom_msg = await db.get_start_message()
    has_custom = bool(custom_msg)

    set_btn_text = "🔄 Change Message" if has_custom else "➕ Set Message"

    buttons = [
        [
            InlineKeyboardButton(set_btn_text, callback_data="start_msg_set"),
            InlineKeyboardButton("👁️ See Message", callback_data="start_msg_see")
        ],
        [
            InlineKeyboardButton("🗑️ Delete Message", callback_data="start_msg_del_confirm")
        ] if has_custom else [],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data="start_config_panel"),
            InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]
    buttons = [b for b in buttons if b]

    if has_custom:
        preview_snippet = custom_msg[:250] + ("..." if len(custom_msg) > 250 else "")
        status_info = (
            "🟢 <b>Status:</b> Custom Active\n\n"
            f"📝 <b>Current Raw Template:</b>\n"
            f"<code>{preview_snippet}</code>\n"
        )
    else:
        status_info = (
            "⚪ <b>Status:</b> Default System Start Message\n\n"
            "<i>Default greeting is currently active.</i>\n"
        )

    text = (
        "💬 <b><u>Start Message Configuration</u></b>\n\n"
        f"{status_info}\n"
        "📌 <b>Available Dynamic Variables:</b>\n"
        "• <code>{mention}</code> - User mention\n"
        "• <code>{first_name}</code> - User first name\n"
        "• <code>{username}</code> - User @username\n"
        "• <code>{id}</code> - User Telegram ID\n"
        "• <code>{greetings}</code> or <code>{gtxt}</code> - Good Morning/Evening greeting\n"
        "• <code>{bot_name}</code> - Bot Name\n"
        "• <code>{bot_username}</code> - Bot Username\n\n"
        "Select an action below:"
    )

    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^start_msg_see$"))
async def start_msg_see_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await query.answer()

    custom_msg = await db.get_start_message()
    _, rendered_preview = await get_start_display_details(query.from_user)

    text = (
        "👁️ <b><u>Start Message Live Preview</u></b>\n\n"
        f"<b>Type:</b> {'🟢 Custom Active' if custom_msg else '⚪ Default Template'}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{rendered_preview}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    if custom_msg:
        text += f"\n📝 <b>Raw Template Code:</b>\n<code>{custom_msg}</code>\n"

    buttons = [
        [
            InlineKeyboardButton("🔄 Change Message", callback_data="start_msg_set") if custom_msg else InlineKeyboardButton("➕ Set Message", callback_data="start_msg_set"),
            InlineKeyboardButton("🗑️ Delete", callback_data="start_msg_del_confirm") if custom_msg else None
        ],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data="start_msg_menu"),
            InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]
    buttons = [[btn for btn in row if btn is not None] for row in buttons]
    buttons = [row for row in buttons if row]

    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^start_msg_set$"))
async def start_msg_set_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await query.answer()

    prompt_text = (
        "✍️ <b><u>Send New Start Message</u></b>\n\n"
        "Please send your new custom Start greeting message now.\n\n"
        "💡 <b>You can use HTML tags (bold, italic, links, etc.) and these placeholders:</b>\n"
        "• <code>{mention}</code> - User's clickable mention\n"
        "• <code>{first_name}</code> - User's first name\n"
        "• <code>{username}</code> - User's @username\n"
        "• <code>{id}</code> - User ID\n"
        "• <code>{greetings}</code> - Time-based greeting (Good morning/night)\n"
        "• <code>{bot_name}</code> - Bot Name\n"
        "• <code>{bot_username}</code> - Bot @Username\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👉 <i>Send the text directly in chat, or click Cancel below:</i>"
    )

    buttons = [
        [
            InlineKeyboardButton("❌ Cancel", callback_data="start_msg_cancel")
        ]
    ]

    await safe_edit_or_replace(client, query.message, prompt_text, reply_markup=InlineKeyboardMarkup(buttons))
    AWAITING_START_MSG[query.from_user.id] = {"state": True, "prompt_msg_id": query.message.id}


@Client.on_callback_query(filters.regex(r"^start_msg_del_confirm$"))
async def start_msg_del_confirm_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await query.answer()

    text = (
        "⚠️ <b><u>Delete Custom Start Message?</u></b>\n\n"
        "Are you sure you want to delete the custom start message?\n\n"
        "🔄 The bot will revert to the default system start message."
    )

    buttons = [
        [
            InlineKeyboardButton("🗑️ Yes, Delete Message", callback_data="start_msg_del_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="start_msg_menu")
        ]
    ]

    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^start_msg_del_yes$"))
async def start_msg_del_yes_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await db.delete_start_message()
    await query.answer("✅ Custom start message deleted! Reverted to default.", show_alert=True)
    return await start_msg_menu_cb(client, query)


@Client.on_callback_query(filters.regex(r"^start_msg_cancel$"))
async def start_msg_cancel_cb(client: Client, query: CallbackQuery):
    AWAITING_START_MSG.pop(query.from_user.id, None)
    await query.answer("Cancelled")
    return await start_msg_menu_cb(client, query)


# =========================================================================
# 3. Start Photo Sub-Menu & Actions
# =========================================================================

@Client.on_callback_query(filters.regex(r"^start_photo_menu$"))
async def start_photo_menu_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    AWAITING_START_PHOTO.pop(query.from_user.id, None)
    await query.answer()

    custom_photo = await db.get_start_photo()
    has_custom = bool(custom_photo)

    set_btn_text = "🔄 Change Photo" if has_custom else "➕ Set Photo"

    buttons = [
        [
            InlineKeyboardButton(set_btn_text, callback_data="start_photo_set"),
            InlineKeyboardButton("👁️ See Photo", callback_data="start_photo_see")
        ],
        [
            InlineKeyboardButton("🗑️ Delete Photo", callback_data="start_photo_del_confirm")
        ] if has_custom else [],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data="start_config_panel"),
            InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]
    buttons = [b for b in buttons if b]

    if has_custom:
        status_info = (
            "🟢 <b>Status:</b> Custom Photo Active\n"
            f"🖼️ <b>Photo Reference:</b> <code>{custom_photo[:45]}...</code>\n"
        )
    else:
        status_info = (
            "⚪ <b>Status:</b> Default Random System Photos Active\n"
            "<i>(Rotates between system PICS automatically)</i>\n"
        )

    text = (
        "📸 <b><u>Start Photo Configuration</u></b>\n\n"
        f"{status_info}\n"
        "Choose an action below to set a custom photo, preview the active image, or reset to default:"
    )

    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^start_photo_see$"))
async def start_photo_see_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await query.answer()

    custom_photo = await db.get_start_photo()
    active_photo, _ = await get_start_display_details(query.from_user)

    caption_text = (
        "👁️ <b><u>Start Photo Preview</u></b>\n\n"
        f"<b>Type:</b> {'🟢 Custom Active' if custom_photo else '⚪ Default Random System Photo'}\n"
    )

    buttons = [
        [
            InlineKeyboardButton("🔄 Change Photo", callback_data="start_photo_set") if custom_photo else InlineKeyboardButton("➕ Set Photo", callback_data="start_photo_set"),
            InlineKeyboardButton("🗑️ Delete Photo", callback_data="start_photo_del_confirm") if custom_photo else None
        ],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data="start_photo_menu"),
            InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]
    buttons = [[b for b in row if b is not None] for row in buttons]
    buttons = [row for row in buttons if row]

    try:
        await query.message.delete()
    except Exception:
        pass

    try:
        await client.send_photo(
            chat_id=query.message.chat.id,
            photo=active_photo,
            caption=caption_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error sending start photo preview: {e}")
        await client.send_message(
            chat_id=query.message.chat.id,
            text=f"{caption_text}\n⚠️ <i>Failed to load photo media ({e}). Current Link:</i> <code>{active_photo}</code>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )


@Client.on_callback_query(filters.regex(r"^start_photo_set$"))
async def start_photo_set_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await query.answer()

    prompt_text = (
        "🖼️ <b><u>Send New Start Photo</u></b>\n\n"
        "Please send the photo you want to display on <code>/start</code>:\n\n"
        "• <b>Option 1:</b> Directly upload a <b>Photo / Image</b> here in chat.\n"
        "• <b>Option 2:</b> Send a direct <b>Image URL / Telegraph Link</b> (e.g. <code>https://graph.org/...</code>).\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👉 <i>Send image or link now, or click Cancel:</i>"
    )

    buttons = [
        [
            InlineKeyboardButton("❌ Cancel", callback_data="start_photo_cancel")
        ]
    ]

    await safe_edit_or_replace(client, query.message, prompt_text, reply_markup=InlineKeyboardMarkup(buttons))
    AWAITING_START_PHOTO[query.from_user.id] = {"state": True, "prompt_msg_id": query.message.id}


@Client.on_callback_query(filters.regex(r"^start_photo_del_confirm$"))
async def start_photo_del_confirm_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await query.answer()

    text = (
        "⚠️ <b><u>Delete Custom Start Photo?</u></b>\n\n"
        "Are you sure you want to delete the custom start photo?\n\n"
        "🔄 The bot will revert to default random system photos."
    )

    buttons = [
        [
            InlineKeyboardButton("🗑️ Yes, Delete Photo", callback_data="start_photo_del_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="start_photo_menu")
        ]
    ]

    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^start_photo_del_yes$"))
async def start_photo_del_yes_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await db.delete_start_photo()
    await query.answer("✅ Custom start photo deleted! Reverted to default.", show_alert=True)
    return await start_photo_menu_cb(client, query)


@Client.on_callback_query(filters.regex(r"^start_photo_cancel$"))
async def start_photo_cancel_cb(client: Client, query: CallbackQuery):
    AWAITING_START_PHOTO.pop(query.from_user.id, None)
    await query.answer("Cancelled")
    return await start_photo_menu_cb(client, query)


# =========================================================================
# 4. Message Listeners for Setting Start Message & Photo
# =========================================================================

@Client.on_message(filters.private & filters.incoming & (filters.text | filters.photo), group=25)
async def admin_start_input_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    # Handle /cancel command cleanly
    if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
        if user_id in AWAITING_START_MSG:
            prompt_info = AWAITING_START_MSG.pop(user_id, None)
            try:
                await message.delete()
            except Exception:
                pass
            if prompt_info and prompt_info.get("prompt_msg_id"):
                try:
                    await client.delete_messages(chat_id=message.chat.id, message_ids=[prompt_info["prompt_msg_id"]])
                except Exception:
                    pass
            text = "❌ <b>Start Message configuration cancelled.</b>"
            buttons = [[InlineKeyboardButton("💬 Start Message Menu", callback_data="start_msg_menu")]]
            await client.send_message(chat_id=message.chat.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
            return

        if user_id in AWAITING_START_PHOTO:
            prompt_info = AWAITING_START_PHOTO.pop(user_id, None)
            try:
                await message.delete()
            except Exception:
                pass
            if prompt_info and prompt_info.get("prompt_msg_id"):
                try:
                    await client.delete_messages(chat_id=message.chat.id, message_ids=[prompt_info["prompt_msg_id"]])
                except Exception:
                    pass
            text = "❌ <b>Start Photo configuration cancelled.</b>"
            buttons = [[InlineKeyboardButton("📸 Start Photo Menu", callback_data="start_photo_menu")]]
            await client.send_message(chat_id=message.chat.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
            return

    # 1. Processing Start Message Input
    if user_id in AWAITING_START_MSG:
        prompt_info = AWAITING_START_MSG.pop(user_id, None)
        new_text = message.text

        if not new_text or new_text.startswith("/"):
            return

        # Auto clean admin input and prompt
        try:
            await message.delete()
        except Exception:
            pass
        if prompt_info and prompt_info.get("prompt_msg_id"):
            try:
                await client.delete_messages(chat_id=message.chat.id, message_ids=[prompt_info["prompt_msg_id"]])
            except Exception:
                pass

        await db.set_start_message(new_text)

        _, rendered = await get_start_display_details(message.from_user)

        success_text = (
            "✅ <b><u>Start Message Updated Successfully!</u></b>\n\n"
            "Here is how your Start greeting will look:\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{rendered}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 <b>Raw Template Saved:</b>\n"
            f"<code>{new_text}</code>"
        )

        buttons = [
            [
                InlineKeyboardButton("👁️ See Live Preview", callback_data="start_msg_see"),
                InlineKeyboardButton("🔄 Change Again", callback_data="start_msg_set")
            ],
            [
                InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ꜱᴛᴀʀᴛ ꜱᴇᴛᴛɪɴɢꜱ", callback_data="start_config_panel"),
                InlineKeyboardButton("⚙️ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", callback_data="admin_settings")
            ]
        ]
        await client.send_message(
            chat_id=message.chat.id,
            text=success_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
        return

    # 2. Processing Start Photo Input
    if user_id in AWAITING_START_PHOTO:
        prompt_info = AWAITING_START_PHOTO.pop(user_id, None)
        photo_ref = None

        if message.photo:
            photo_ref = message.photo.file_id
        elif message.text:
            text_str = message.text.strip()
            if text_str.startswith("http://") or text_str.startswith("https://"):
                photo_ref = text_str
            else:
                try:
                    await message.delete()
                except Exception:
                    pass
                if prompt_info and prompt_info.get("prompt_msg_id"):
                    try:
                        await client.delete_messages(chat_id=message.chat.id, message_ids=[prompt_info["prompt_msg_id"]])
                    except Exception:
                        pass
                err_text = (
                    "❌ <b>Invalid Photo Input!</b>\n\n"
                    "Please provide a valid image file or direct HTTP/HTTPS image URL."
                )
                buttons = [[InlineKeyboardButton("🔄 Try Again", callback_data="start_photo_set")]]
                await client.send_message(chat_id=message.chat.id, text=err_text, reply_markup=InlineKeyboardMarkup(buttons))
                return

        if not photo_ref:
            return

        # Auto clean admin input and prompt
        try:
            await message.delete()
        except Exception:
            pass
        if prompt_info and prompt_info.get("prompt_msg_id"):
            try:
                await client.delete_messages(chat_id=message.chat.id, message_ids=[prompt_info["prompt_msg_id"]])
            except Exception:
                pass

        await db.set_start_photo(photo_ref)

        success_text = (
            "✅ <b><u>Start Photo Updated Successfully!</u></b>\n\n"
            "Your new Start photo is now active for all incoming <code>/start</code> commands."
        )

        buttons = [
            [
                InlineKeyboardButton("👁️ See Photo Preview", callback_data="start_photo_see"),
                InlineKeyboardButton("🔄 Change Again", callback_data="start_photo_set")
            ],
            [
                InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ꜱᴛᴀʀᴛ ꜱᴇᴛᴛɪɴɢꜱ", callback_data="start_config_panel"),
                InlineKeyboardButton("⚙️ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", callback_data="admin_settings")
            ]
        ]

        try:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=photo_ref,
                caption=success_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error confirming start photo: {e}")
            await client.send_message(
                chat_id=message.chat.id,
                text=f"{success_text}\n\nPhoto Link: <code>{photo_ref}</code>",
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
        return
