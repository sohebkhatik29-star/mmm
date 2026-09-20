import logging
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)
from database.users_chats_db import db
from info import ADMINS, CUSTOM_FILE_CAPTION
from utils import temp

logger = logging.getLogger(__name__)

# State tracking for admin setting custom caption: {user_id: {"state": True, "prompt_msg_id": int}}
AWAITING_CAPTION = {}

def is_admin(user_id: int) -> bool:
    try:
        uid = int(user_id)
        return uid in ADMINS or str(uid) in [str(a) for a in ADMINS]
    except Exception:
        return False


def get_caption_main_markup(has_custom: bool = False) -> InlineKeyboardMarkup:
    set_btn_text = "🔄 Change Caption" if has_custom else "➕ Set Caption"
    buttons = [
        [
            InlineKeyboardButton(set_btn_text, callback_data="caption_set"),
            InlineKeyboardButton("👁️ See Caption", callback_data="caption_see")
        ],
        [
            InlineKeyboardButton("🗑️ Delete Caption", callback_data="caption_del_confirm")
        ] if has_custom else [],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴀᴅᴍɪɴ", callback_data="admin_settings"),
            InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]
    # Remove empty rows if any
    buttons = [row for row in buttons if row]
    return InlineKeyboardMarkup(buttons)


async def safe_edit_or_replace(client: Client, message: Message, text: str, reply_markup: InlineKeyboardMarkup = None, disable_web_page_preview: bool = True):
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


# =========================================================================
# Caption Management Main Panel
# =========================================================================

@Client.on_message(filters.command(["caption", "file_caption", "custom_caption"]) & filters.private)
async def caption_panel_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    AWAITING_CAPTION.pop(message.from_user.id, None)
    custom_caption = await db.get_bot_caption()
    has_custom = bool(custom_caption)

    text = (
        "📝 <b><u>File Caption Management (Captain)</u></b>\n\n"
        f"📊 <b>Current Status:</b> {'✅ <b>Custom Caption Active</b>' if has_custom else '⚙️ <b>Default Caption Active</b>'}\n\n"
        "Yahan se aap movies/files ke sath jane wali caption ko customize kar sakte hain:\n\n"
        "• <b>Set Caption:</b> Nayi custom caption banayein\n"
        "• <b>See Caption:</b> Current caption & preview dekhein\n"
        "• <b>Delete Caption:</b> Custom caption hata kar default par reset karein"
    )
    await message.reply_text(text, reply_markup=get_caption_main_markup(has_custom))


@Client.on_callback_query(filters.regex(r"^caption_panel$"))
async def caption_panel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    AWAITING_CAPTION.pop(query.from_user.id, None)
    custom_caption = await db.get_bot_caption()
    has_custom = bool(custom_caption)

    text = (
        "📝 <b><u>File Caption Management (Captain)</u></b>\n\n"
        f"📊 <b>Current Status:</b> {'✅ <b>Custom Caption Active</b>' if has_custom else '⚙️ <b>Default Caption Active</b>'}\n\n"
        "Yahan se aap movies/files ke sath jane wali caption ko customize kar sakte hain:\n\n"
        "• <b>Set Caption:</b> Nayi custom caption banayein\n"
        "• <b>See Caption:</b> Current caption & preview dekhein\n"
        "• <b>Delete Caption:</b> Custom caption hata kar default par reset karein"
    )
    await safe_edit_or_replace(client, query.message, text, reply_markup=get_caption_main_markup(has_custom))
    await query.answer()


# =========================================================================
# 1. 👁️ See Caption (View Current Caption & Live Sample Preview)
# =========================================================================

@Client.on_message(filters.command(["see_caption", "seecaption"]) & filters.private)
async def see_caption_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    custom_caption = await db.get_bot_caption()
    active_caption = custom_caption if custom_caption else CUSTOM_FILE_CAPTION
    is_custom = bool(custom_caption)

    sample_name = "Avengers Endgame (2019) 1080p WEB-DL x264.mkv"
    sample_size = "2.45 GB"
    sample_fcap = "Dual Audio [Hindi + English]"

    try:
        preview = active_caption.format(
            file_name=sample_name,
            file_size=sample_size,
            file_caption=sample_fcap
        )
    except Exception:
        preview = active_caption

    text = (
        "👁️ <b><u>Current File Caption Details</u></b>\n\n"
        f"📌 <b>Status:</b> {'✅ <b>Custom Caption</b>' if is_custom else '⚙️ <b>Default System Caption</b>'}\n\n"
        f"📜 <b>Raw Template:</b>\n<code>{active_caption}</code>\n\n"
        f"🔍 <b>Live Sample Preview:</b>\n<blockquote>{preview}</blockquote>\n\n"
        "📌 <b>Available Variables for Template:</b>\n"
        "• <code>{file_name}</code> - File ka naam\n"
        "• <code>{file_size}</code> - File ka size (e.g. 1.2 GB)\n"
        "• <code>{file_caption}</code> - Telegram file ki original caption"
    )

    buttons = [
        [
            InlineKeyboardButton("🔄 Change Caption" if is_custom else "➕ Set Caption", callback_data="caption_set")
        ]
    ]
    if is_custom:
        buttons.append([InlineKeyboardButton("🗑️ Delete Caption", callback_data="caption_del_confirm")])
    buttons.append([
        InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴄᴀᴘᴛɪᴏɴ", callback_data="caption_panel"),
        InlineKeyboardButton("« ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", callback_data="admin_settings")
    ])

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^caption_see$"))
async def see_caption_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    custom_caption = await db.get_bot_caption()
    active_caption = custom_caption if custom_caption else CUSTOM_FILE_CAPTION
    is_custom = bool(custom_caption)

    sample_name = "Avengers Endgame (2019) 1080p WEB-DL x264.mkv"
    sample_size = "2.45 GB"
    sample_fcap = "Dual Audio [Hindi + English]"

    try:
        preview = active_caption.format(
            file_name=sample_name,
            file_size=sample_size,
            file_caption=sample_fcap
        )
    except Exception:
        preview = active_caption

    text = (
        "👁️ <b><u>Current File Caption Details</u></b>\n\n"
        f"📌 <b>Status:</b> {'✅ <b>Custom Caption</b>' if is_custom else '⚙️ <b>Default System Caption</b>'}\n\n"
        f"📜 <b>Raw Template:</b>\n<code>{active_caption}</code>\n\n"
        f"🔍 <b>Live Sample Preview:</b>\n<blockquote>{preview}</blockquote>\n\n"
        "📌 <b>Available Variables for Template:</b>\n"
        "• <code>{file_name}</code> - File ka naam\n"
        "• <code>{file_size}</code> - File ka size (e.g. 1.2 GB)\n"
        "• <code>{file_caption}</code> - Telegram file ki original caption"
    )

    buttons = [
        [
            InlineKeyboardButton("🔄 Change Caption" if is_custom else "➕ Set Caption", callback_data="caption_set")
        ]
    ]
    if is_custom:
        buttons.append([InlineKeyboardButton("🗑️ Delete Caption", callback_data="caption_del_confirm")])
    buttons.append([
        InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴄᴀᴘᴛɪᴏɴ", callback_data="caption_panel"),
        InlineKeyboardButton("« ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", callback_data="admin_settings")
    ])

    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


# =========================================================================
# 2. ➕ Set Caption (Add/Update Custom Caption)
# =========================================================================

@Client.on_message(filters.command(["set_caption", "setcaption"]) & filters.private)
async def set_caption_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    text = (
        "➕ <b><u>Set Custom File Caption (Captain)</u></b>\n\n"
        "👉 <b>Apna naya caption template yahan type karke bhejein:</b>\n\n"
        "📌 <b>Aap in variables ka use kar sakte hain:</b>\n"
        "• <code>{file_name}</code> - File ka exact name aayega\n"
        "• <code>{file_size}</code> - File ka human-readable size\n"
        "• <code>{file_caption}</code> - File ki original caption (if any)\n\n"
        "<b>Example Template:</b>\n"
        "<code>🎬 <b>{file_name}</b>\n\n💾 <b>Size:</b> {file_size}\n\n🍿 <b>Join:</b> @MoviesGroupG3</code>\n\n"
        "Send /cancel to cancel."
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="caption_panel")]]
    prompt_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    AWAITING_CAPTION[message.from_user.id] = {
        "state": True,
        "prompt_msg_id": prompt_msg.id
    }


@Client.on_callback_query(filters.regex(r"^caption_set$"))
async def set_caption_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    AWAITING_CAPTION[query.from_user.id] = {
        "state": True,
        "prompt_msg_id": query.message.id
    }
    text = (
        "➕ <b><u>Set Custom File Caption (Captain)</u></b>\n\n"
        "👉 <b>Apna naya caption template yahan type karke bhejein:</b>\n\n"
        "📌 <b>Aap in variables ka use kar sakte hain:</b>\n"
        "• <code>{file_name}</code> - File ka exact name aayega\n"
        "• <code>{file_size}</code> - File ka human-readable size\n"
        "• <code>{file_caption}</code> - File ki original caption (if any)\n\n"
        "<b>Example Template:</b>\n"
        "<code>🎬 <b>{file_name}</b>\n\n💾 <b>Size:</b> {file_size}\n\n🍿 <b>Join:</b> @MoviesGroupG3</code>\n\n"
        "Send /cancel to cancel."
    )
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="caption_panel")]]
    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_message(filters.private & ~filters.bot & filters.incoming, group=3)
async def handle_caption_admin_input(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    caption_data = AWAITING_CAPTION.get(user_id)
    if not caption_data:
        return

    prompt_msg_id = caption_data.get("prompt_msg_id") if isinstance(caption_data, dict) else None

    # Helper to clean up previous input and prompt message
    async def cleanup_input_and_prompt():
        try:
            await message.delete()
        except Exception:
            pass
        if prompt_msg_id:
            try:
                await client.delete_messages(chat_id=message.chat.id, message_ids=prompt_msg_id)
            except Exception:
                pass

    # Check for cancel
    if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
        AWAITING_CAPTION.pop(user_id, None)
        await cleanup_input_and_prompt()
        buttons = [[InlineKeyboardButton("« Back to Caption", callback_data="caption_panel")]]
        return await client.send_message(
            chat_id=message.chat.id,
            text="🚫 <b>Caption editing cancelled.</b>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    if not message.text:
        return await message.reply_text("❌ <b>Invalid Input!</b> Kripya text template bhejein.\nSend /cancel to cancel.")

    new_caption = message.text.html if hasattr(message.text, 'html') else message.text
    try:
        await db.set_bot_caption(new_caption)
        # Clear settings cache so new caption applies immediately everywhere
        temp.SETTINGS.clear()
        AWAITING_CAPTION.pop(user_id, None)

        await cleanup_input_and_prompt()

        sample_name = "Avengers Endgame (2019) 1080p.mkv"
        sample_size = "2.45 GB"
        sample_fcap = "Dual Audio [Hindi+Eng]"
        try:
            preview = new_caption.format(
                file_name=sample_name,
                file_size=sample_size,
                file_caption=sample_fcap
            )
        except Exception:
            preview = new_caption

        success_text = (
            "✅ <b><u>Custom File Caption Saved Successfully!</u></b>\n\n"
            f"📜 <b>New Template:</b>\n<code>{new_caption}</code>\n\n"
            f"🔍 <b>Live Preview Example:</b>\n<blockquote>{preview}</blockquote>\n\n"
            "✨ <i>Ab jab bhi koi user file download karega, usko yehi customized caption milegi!</i>"
        )
        buttons = [
            [
                InlineKeyboardButton("👁️ See Caption", callback_data="caption_see"),
                InlineKeyboardButton("🔄 Change Caption", callback_data="caption_set")
            ],
            [
                InlineKeyboardButton("« Back to Caption", callback_data="caption_panel"),
                InlineKeyboardButton("« Admin Panel", callback_data="admin_settings")
            ]
        ]
        await client.send_message(
            chat_id=message.chat.id,
            text=success_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.exception("Error saving custom caption: %s", e)
        await message.reply_text(f"❌ <b>Database Error:</b> <code>{e}</code>")


# =========================================================================
# 3. 🗑️ Delete Caption (Reset to Default)
# =========================================================================

@Client.on_message(filters.command(["del_caption", "delcaption", "delete_caption"]) & filters.private)
async def del_caption_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("⛔️ <b>Access Denied:</b> Administrators only.")
    
    AWAITING_CAPTION.pop(message.from_user.id, None)
    buttons = [
        [
            InlineKeyboardButton("⚠️ Yes, Delete Custom Caption", callback_data="caption_del_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="caption_panel")
        ]
    ]
    await message.reply_text(
        "⚠️ <b><u>Confirmation Required</u></b>\n\n"
        "Kya aap sach me <b>Custom Caption ko delete</b> karke default par reset karna chahte hain?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_callback_query(filters.regex(r"^caption_del_confirm$"))
async def caption_del_confirm_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    buttons = [
        [
            InlineKeyboardButton("⚠️ Yes, Delete Custom Caption", callback_data="caption_del_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="caption_panel")
        ]
    ]
    text = (
        "⚠️ <b><u>Confirmation Required</u></b>\n\n"
        "Kya aap sach me <b>Custom Caption ko delete</b> karke default par reset karna chahte hain?"
    )
    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^caption_del_yes$"))
async def caption_del_yes_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)
    
    await db.delete_bot_caption()
    temp.SETTINGS.clear()
    await query.answer("✅ Custom Caption deleted! Default caption restored.", show_alert=True)

    text = (
        "✅ <b><u>Caption Reset to Default</u></b>\n\n"
        "Custom caption successfully delete ho gayi hai aur system ki default caption restore kar di gayi hai."
    )
    buttons = [
        [InlineKeyboardButton("➕ Set New Caption", callback_data="caption_set")],
        [
            InlineKeyboardButton("« Back to Caption", callback_data="caption_panel"),
            InlineKeyboardButton("« Admin Panel", callback_data="admin_settings")
        ]
    ]
    await safe_edit_or_replace(client, query.message, text, reply_markup=InlineKeyboardMarkup(buttons))
