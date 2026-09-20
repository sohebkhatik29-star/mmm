import logging
import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)
from database.users_chats_db import db
from info import ADMINS, INITIAL_ADMINS

logger = logging.getLogger(__name__)

# State tracking for user inputs
AWAITING_ADD_ADMIN = {}   # {admin_id: prompt_message_id}
AWAITING_DEL_ADMIN = {}   # {admin_id: prompt_message_id}


def is_admin(user_id: int) -> bool:
    try:
        uid = int(user_id)
        return uid in ADMINS or str(uid) in [str(a) for a in ADMINS]
    except Exception:
        return False


def get_manage_admins_markup() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("➕ ᴀᴅᴅ ᴀᴅᴍɪɴ", callback_data="manage_admin_add"),
            InlineKeyboardButton("👁️ ꜱᴇᴇ ᴀᴅᴍɪɴꜱ", callback_data="manage_admin_see")
        ],
        [
            InlineKeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ ᴀᴅᴍɪɴ", callback_data="manage_admin_del")
        ],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ꜱᴇᴛᴛɪɴɢꜱ", callback_data="admin_settings"),
            InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


# =========================================================================
# Main Manage Admins Panel
# =========================================================================

@Client.on_callback_query(filters.regex(r"^manage_admins_panel$"))
async def manage_admins_panel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied! Only bot administrators can access this menu.", show_alert=True)

    # Cancel any pending input state for this admin
    AWAITING_ADD_ADMIN.pop(query.from_user.id, None)
    AWAITING_DEL_ADMIN.pop(query.from_user.id, None)

    custom_admins = await db.get_all_custom_admins()
    primary_count = len(INITIAL_ADMINS)
    custom_count = len(custom_admins)
    total_count = len(ADMINS)

    text = (
        "👥 <b><u>Admin Management Panel</u></b>\n\n"
        "Yaha se aap naye Admins add kar sakte hain, existing Admins dekh sakte hain, aur unhe remove kar sakte hain.\n\n"
        f"👑 <b>Primary/Owner Admins:</b> <code>{primary_count}</code>\n"
        f"⭐ <b>Custom Database Admins:</b> <code>{custom_count}</code>\n"
        f"📊 <b>Total Active Admins:</b> <code>{total_count}</code>\n\n"
        "💡 <i>Naye admin ko bot ki sabhi settings aur controls ka full access milega aur use bot me direct notification message jayega.</i>\n\n"
        "Niche diye gaye options me se select karein:"
    )

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=get_manage_admins_markup(),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass
    await query.answer()


# =========================================================================
# See Admins List
# =========================================================================

@Client.on_callback_query(filters.regex(r"^manage_admin_see$"))
async def manage_admin_see_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    custom_admins = await db.get_all_custom_admins()

    text = "👥 <b><u>Active Bot Administrators List</u></b>\n\n"

    # Primary Admins
    text += "👑 <b><u>Owner / Primary Admins:</u></b>\n"
    for i, p_admin in enumerate(INITIAL_ADMINS, 1):
        try:
            p_uid = int(p_admin)
            text += f"{i}. 🆔 <code>{p_uid}</code> <i>(Config/Env Admin)</i>\n"
        except Exception:
            text += f"{i}. <code>{p_admin}</code>\n"
    
    text += "\n⭐ <b><u>Custom Added Admins:</u></b>\n"
    if custom_admins:
        for idx, adm in enumerate(custom_admins, 1):
            uid = adm.get('user_id')
            uname = adm.get('username')
            uname_str = f"@{uname}" if uname else "<i>None</i>"
            name = adm.get('name') or "Admin"
            added_at = adm.get('added_at')
            date_str = added_at.strftime("%d-%m-%Y %H:%M") if added_at else "N/A"
            text += (
                f"{idx}. <b>{name}</b> ({uname_str})\n"
                f"   🆔 <code>{uid}</code> | 📅 {date_str}\n"
            )
    else:
        text += "<i>No custom admins added yet.</i>\n"

    text += (
        f"\n📊 <b>Total Active Admins:</b> <code>{len(ADMINS)}</code>\n"
    )

    buttons = [
        [
            InlineKeyboardButton("➕ ᴀᴅᴅ ᴀᴅᴍɪɴ", callback_data="manage_admin_add"),
            InlineKeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ ᴀᴅᴍɪɴ", callback_data="manage_admin_del")
        ],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴍᴀɴᴀɢᴇ", callback_data="manage_admins_panel"),
            InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass
    await query.answer()


# =========================================================================
# Add Admin Prompt
# =========================================================================

@Client.on_callback_query(filters.regex(r"^manage_admin_add$"))
async def manage_admin_add_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    AWAITING_DEL_ADMIN.pop(query.from_user.id, None)
    AWAITING_ADD_ADMIN[query.from_user.id] = query.message.id

    text = (
        "➕ <b><u>Add New Bot Administrator</u></b>\n\n"
        "👉 Please send the <b>Telegram User ID</b> (e.g. <code>1234567890</code>) ya <b>@username</b> (e.g. <code>@john_doe</code>).\n\n"
        "💡 <i>Aap us user ka koi bhi message is chat me <b>Forward</b> bhi kar sakte hain.</i>\n\n"
        "✨ <b>Permissions:</b> Naye admin ke paas bot ki <b>har setting</b> (FSub, Captions, Start Settings, Broadcast etc.) ka full access hoga aur use bot ke andar congratulatory notification message jayega.\n\n"
        "<i>Cancel karne ke liye niche Cancel button dabayein.</i>"
    )

    buttons = [
        [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="manage_admin_cancel")]
    ]

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass
    await query.answer()


# =========================================================================
# Delete Admin Prompt & List
# =========================================================================

@Client.on_callback_query(filters.regex(r"^manage_admin_del$"))
async def manage_admin_del_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    AWAITING_ADD_ADMIN.pop(query.from_user.id, None)
    custom_admins = await db.get_all_custom_admins()

    if not custom_admins:
        text = (
            "🗑️ <b><u>Delete Administrator</u></b>\n\n"
            "ℹ️ <b>Koi bhi Custom Admin nahi mila!</b>\n\n"
            "<i>Note: Primary/Owner (config/env) admins ko delete nahi kiya ja sakta.</i>"
        )
        buttons = [
            [InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴍᴀɴᴀɢᴇ", callback_data="manage_admins_panel")]
        ]
        try:
            await query.message.edit_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass
        return await query.answer("No custom admins to delete!", show_alert=True)

    AWAITING_DEL_ADMIN[query.from_user.id] = query.message.id

    text = (
        "🗑️ <b><u>Delete Administrator</u></b>\n\n"
        "Niche diye gaye buttons se kisi bhi admin ko directly remove karein ya unka <b>User ID / Username</b> chat me send karein:\n"
    )

    buttons = []
    for adm in custom_admins:
        uid = adm.get('user_id')
        name = adm.get('name') or "Admin"
        uname = f"@{adm.get('username')}" if adm.get('username') else str(uid)
        buttons.append([
            InlineKeyboardButton(
                f"🗑️ Remove {name[:12]} ({uname[:12]})",
                callback_data=f"manage_del_confirm_{uid}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="manage_admin_cancel")
    ])

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass
    await query.answer()


# =========================================================================
# Delete Specific Admin Confirmation & Execution
# =========================================================================

@Client.on_callback_query(filters.regex(r"^manage_del_confirm_(\d+)$"))
async def manage_del_confirm_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    target_uid = int(query.matches[0].group(1))
    admin_doc = await db.get_custom_admin(target_uid)

    name = admin_doc.get('name', 'Admin') if admin_doc else "Admin"
    uname = f"@{admin_doc.get('username')}" if admin_doc and admin_doc.get('username') else "N/A"

    text = (
        f"⚠️ <b><u>Confirm Admin Deletion</u></b>\n\n"
        f"Kya aap sach me <b>{name}</b> ({uname}) ko Admin se hatana chahte hain?\n\n"
        f"🆔 <b>User ID:</b> <code>{target_uid}</code>"
    )

    buttons = [
        [
            InlineKeyboardButton("✅ ʏᴇꜱ, ʀᴇᴍᴏᴠᴇ", callback_data=f"manage_del_yes_{target_uid}"),
            InlineKeyboardButton("❌ ɴᴏ, ᴄᴀɴᴄᴇʟ", callback_data="manage_admin_del")
        ]
    ]

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass
    await query.answer()


@Client.on_callback_query(filters.regex(r"^manage_del_yes_(\d+)$"))
async def manage_del_yes_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    target_uid = int(query.matches[0].group(1))
    AWAITING_DEL_ADMIN.pop(query.from_user.id, None)

    if target_uid in INITIAL_ADMINS:
        return await query.answer("⛔ Cannot remove Primary/Owner admin!", show_alert=True)

    success = await db.remove_custom_admin(target_uid)

    # Send notification to removed user
    try:
        await client.send_message(
            chat_id=target_uid,
            text=(
                "ℹ️ <b><u>Admin Privileges Revoked</u></b>\n\n"
                "Aapki is bot se Administrator privileges remove kar di gayi hain."
            ),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass

    text = (
        "✅ <b><u>Admin Removed Successfully!</u></b>\n\n"
        f"User ID <code>{target_uid}</code> ko successfully administrator privileges se hata diya gaya hai."
    )

    buttons = [
        [
            InlineKeyboardButton("👁️ ꜱᴇᴇ ᴀᴅᴍɪɴꜱ", callback_data="manage_admin_see"),
            InlineKeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ ᴀɴᴏᴛʜᴇʀ", callback_data="manage_admin_del")
        ],
        [
            InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴍᴀɴᴀɢᴇ", callback_data="manage_admins_panel"),
            InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
        ]
    ]

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass
    await query.answer("Admin Removed!", show_alert=False)


# =========================================================================
# Cancel Callback
# =========================================================================

@Client.on_callback_query(filters.regex(r"^manage_admin_cancel$"))
async def manage_admin_cancel_cb(client: Client, query: CallbackQuery):
    AWAITING_ADD_ADMIN.pop(query.from_user.id, None)
    AWAITING_DEL_ADMIN.pop(query.from_user.id, None)
    await manage_admins_panel_cb(client, query)


# =========================================================================
# Message Handler for Adding & Deleting Admins (group=26)
# =========================================================================

@Client.on_message(filters.private & filters.incoming, group=26)
async def manage_admin_message_handler(client: Client, message: Message):
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        return

    # Check if admin is currently awaiting Add Admin input
    if admin_id in AWAITING_ADD_ADMIN:
        prompt_msg_id = AWAITING_ADD_ADMIN.pop(admin_id, None)

        # Allow user to cancel by command
        if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
            try:
                await message.delete()
            except Exception:
                pass
            if prompt_msg_id:
                try:
                    await client.edit_message_text(
                        chat_id=admin_id,
                        message_id=prompt_msg_id,
                        text="❌ <b>Action Cancelled.</b>",
                        reply_markup=get_manage_admins_markup(),
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    pass
            return

        target_user = None
        target_uid = None
        target_name = "Admin"
        target_username = None

        # Check if forwarded
        if message.forward_from:
            target_uid = message.forward_from.id
            target_name = message.forward_from.first_name or "Admin"
            target_username = message.forward_from.username
        else:
            raw_input = message.text.strip() if message.text else ""
            if not raw_input:
                return

            # If integer ID
            if raw_input.lstrip("-").isdigit():
                target_uid = int(raw_input)
                try:
                    target_user = await client.get_users(target_uid)
                    target_name = target_user.first_name or "Admin"
                    target_username = target_user.username
                except Exception:
                    # User might not have interacted with bot directly yet
                    db_user = await db.get_user(target_uid)
                    if db_user:
                        target_name = db_user.get('name', 'Admin')
            else:
                # Username lookup
                cleaned_username = raw_input.replace("@", "").strip()
                try:
                    target_user = await client.get_users(cleaned_username)
                    target_uid = target_user.id
                    target_name = target_user.first_name or "Admin"
                    target_username = target_user.username
                except Exception:
                    # Try searching database by username
                    user_in_db = await db.col.find_one({"username": {"$regex": f"^{cleaned_username}$", "$options": "i"}})
                    if user_in_db:
                        target_uid = int(user_in_db.get('id'))
                        target_name = user_in_db.get('name', 'Admin')
                        target_username = cleaned_username

        # Clean up input message and previous prompt
        try:
            await message.delete()
        except Exception:
            pass

        if not target_uid:
            err_text = (
                "❌ <b><u>User Not Found!</u></b>\n\n"
                "Aapka diya gaya User ID ya Username match nahi hua.\n"
                "Kripya sahi Telegram User ID (e.g. <code>1234567890</code>) ya username bhejein."
            )
            buttons = [
                [InlineKeyboardButton("➕ ᴛʀʏ ᴀɢᴀɪɴ", callback_data="manage_admin_add")],
                [InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴍᴀɴᴀɢᴇ", callback_data="manage_admins_panel")]
            ]
            if prompt_msg_id:
                try:
                    return await client.edit_message_text(
                        chat_id=admin_id,
                        message_id=prompt_msg_id,
                        text=err_text,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    pass
            return await client.send_message(
                chat_id=admin_id,
                text=err_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )

        # Check if already admin
        if target_uid in ADMINS:
            already_text = (
                f"⚠️ <b>User Already Admin!</b>\n\n"
                f"👤 <b>Name:</b> {target_name}\n"
                f"🆔 <b>User ID:</b> <code>{target_uid}</code>\n"
                f"🔗 <b>Username:</b> @{target_username or 'None'}\n\n"
                "Yeh user pehle se hi bot administrator hain!"
            )
            buttons = [
                [InlineKeyboardButton("👁️ ꜱᴇᴇ ᴀᴅᴍɪɴꜱ", callback_data="manage_admin_see")],
                [InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴍᴀɴᴀɢᴇ", callback_data="manage_admins_panel")]
            ]
            if prompt_msg_id:
                try:
                    return await client.edit_message_text(
                        chat_id=admin_id,
                        message_id=prompt_msg_id,
                        text=already_text,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    pass
            return await client.send_message(
                chat_id=admin_id,
                text=already_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )

        # Add to DB and active ADMINS
        await db.add_custom_admin(
            user_id=target_uid,
            username=target_username,
            name=target_name,
            added_by=admin_id
        )

        # Send notification to the newly appointed admin
        notified = False
        try:
            bot_me = await client.get_me()
            notify_text = (
                "🎉 <b><u>Congratulations!</u></b>\n\n"
                f"👑 <b>Aapko @{bot_me.username} ka Administrator bana diya gaya hai!</b>\n\n"
                "✨ <i>Ab aapke paas bot ki sabhi Settings aur controls ka full access hai:</i>\n"
                "• 📢 Multi-Channel Force Subscribe\n"
                "• 📝 Custom Caption Settings\n"
                "• 🖼️ Start Text & Photo Settings\n"
                "• 👥 Manage Admins\n"
                "• 📊 Statistics & Broadcast Controls\n\n"
                "👉 Aap /start karke <b>⚙️ Admin Settings</b> access kar sakte hain."
            )
            await client.send_message(
                chat_id=target_uid,
                text=notify_text,
                parse_mode=enums.ParseMode.HTML
            )
            notified = True
        except Exception as e:
            logger.warning(f"Could not send admin notification to {target_uid}: {e}")
            notified = False

        status_msg = "📨 <i>Notification message successfully sent to the user in bot chat.</i>" if notified else "⚠️ <i>User has not started the bot yet, but Admin permissions have been activated!</i>"

        success_text = (
            "✅ <b><u>Admin Added Successfully!</u></b>\n\n"
            f"👤 <b>Name:</b> {target_name}\n"
            f"🆔 <b>User ID:</b> <code>{target_uid}</code>\n"
            f"🔗 <b>Username:</b> @{target_username or 'None'}\n"
            f"👑 <b>Status:</b> Full Administrator\n\n"
            f"{status_msg}"
        )

        buttons = [
            [
                InlineKeyboardButton("👁️ ꜱᴇᴇ ᴀᴅᴍɪɴꜱ", callback_data="manage_admin_see"),
                InlineKeyboardButton("➕ ᴀᴅᴅ ᴀɴᴏᴛʜᴇʀ", callback_data="manage_admin_add")
            ],
            [
                InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴍᴀɴᴀɢᴇ", callback_data="manage_admins_panel"),
                InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
            ]
        ]

        if prompt_msg_id:
            try:
                return await client.edit_message_text(
                    chat_id=admin_id,
                    message_id=prompt_msg_id,
                    text=success_text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                pass

        return await client.send_message(
            chat_id=admin_id,
            text=success_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )

    # Check if admin is currently awaiting Delete Admin input (via typed ID or username)
    elif admin_id in AWAITING_DEL_ADMIN:
        prompt_msg_id = AWAITING_DEL_ADMIN.pop(admin_id, None)

        if message.text and message.text.strip().lower() in ["/cancel", "cancel"]:
            try:
                await message.delete()
            except Exception:
                pass
            if prompt_msg_id:
                try:
                    await client.edit_message_text(
                        chat_id=admin_id,
                        message_id=prompt_msg_id,
                        text="❌ <b>Action Cancelled.</b>",
                        reply_markup=get_manage_admins_markup(),
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    pass
            return

        raw_input = message.text.strip() if message.text else ""
        target_uid = None

        if raw_input.lstrip("-").isdigit():
            target_uid = int(raw_input)
        else:
            uname = raw_input.replace("@", "").strip()
            custom_admins = await db.get_all_custom_admins()
            for adm in custom_admins:
                if adm.get('username', '').lower() == uname.lower():
                    target_uid = adm.get('user_id')
                    break

        try:
            await message.delete()
        except Exception:
            pass

        if not target_uid:
            err_text = (
                "❌ <b><u>Admin Not Found!</u></b>\n\n"
                "Aapka diya gaya User ID ya Username custom admins list me nahi mila."
            )
            buttons = [
                [InlineKeyboardButton("🗑️ ᴛʀʏ ᴀɢᴀɪɴ", callback_data="manage_admin_del")],
                [InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴍᴀɴᴀɢᴇ", callback_data="manage_admins_panel")]
            ]
            if prompt_msg_id:
                try:
                    return await client.edit_message_text(
                        chat_id=admin_id,
                        message_id=prompt_msg_id,
                        text=err_text,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    pass
            return await client.send_message(
                chat_id=admin_id,
                text=err_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )

        if target_uid in INITIAL_ADMINS:
            owner_text = "⛔ <b>Cannot delete Primary Owner / Environment Admin!</b>"
            buttons = [
                [InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴍᴀɴᴀɢᴇ", callback_data="manage_admins_panel")]
            ]
            if prompt_msg_id:
                try:
                    return await client.edit_message_text(
                        chat_id=admin_id,
                        message_id=prompt_msg_id,
                        text=owner_text,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    pass
            return await client.send_message(
                chat_id=admin_id,
                text=owner_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )

        await db.remove_custom_admin(target_uid)

        try:
            await client.send_message(
                chat_id=target_uid,
                text=(
                    "ℹ️ <b><u>Admin Privileges Revoked</u></b>\n\n"
                    "Aapki is bot se Administrator privileges remove kar di gayi hain."
                ),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass

        del_text = (
            "✅ <b><u>Admin Removed Successfully!</u></b>\n\n"
            f"User ID <code>{target_uid}</code> ko successfully administrator privileges se hata diya gaya hai."
        )

        buttons = [
            [
                InlineKeyboardButton("👁️ ꜱᴇᴇ ᴀᴅᴍɪɴꜱ", callback_data="manage_admin_see"),
                InlineKeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ ᴀɴᴏᴛʜᴇʀ", callback_data="manage_admin_del")
            ],
            [
                InlineKeyboardButton("« ʙᴀᴄᴋ ᴛᴏ ᴍᴀɴᴀɢᴇ", callback_data="manage_admins_panel"),
                InlineKeyboardButton("⇋ ʜᴏᴍᴇ ⇋", callback_data="start")
            ]
        ]

        if prompt_msg_id:
            try:
                return await client.edit_message_text(
                    chat_id=admin_id,
                    message_id=prompt_msg_id,
                    text=del_text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                pass

        return await client.send_message(
            chat_id=admin_id,
            text=del_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
