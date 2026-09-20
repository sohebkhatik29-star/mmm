import logging
import re
import datetime
import pytz
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)
from database.users_chats_db import db
from info import ADMINS, LOG_VR_CHANNEL, SHORTENER_WEBSITE, SHORTENER_API, TUTORIAL, SHORTENER_WEBSITE2, SHORTENER_API2, TUTORIAL_2, SHORTENER_WEBSITE3, SHORTENER_API3, TUTORIAL_3, TWO_VERIFY_GAP, THREE_VERIFY_GAP, VERIFY_IMG, IS_VERIFY
from utils import get_readable_time
from Script import script

logger = logging.getLogger(__name__)

# State tracking for interactive admin inputs
AWAITING_VERIFY_INPUT = {}       # {admin_id: {"action": str, "step": int, "prompt_id": int}}
AWAITING_LOG_CHANNEL_INPUT = {}   # {admin_id: prompt_id}

STEP_NAMES = {
    1: {"name": "FIRST", "title": "FIRST TOKEN VERIFICATION", "ord": "FIRST"},
    2: {"name": "SECOND", "title": "SECOND TOKEN VERIFICATION", "ord": "SECOND"},
    3: {"name": "THIRD", "title": "THIRD TOKEN VERIFICATION", "ord": "THIRD"},
}


def is_admin(user_id: int) -> bool:
    try:
        uid = int(user_id)
        return uid in ADMINS or str(uid) in [str(a) for a in ADMINS]
    except Exception:
        return False


def get_main_verify_markup() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🎯 FIRST VERIFICATION", callback_data="vmenu_1")
        ],
        [
            InlineKeyboardButton("🎯 SECOND VERIFICATION", callback_data="vmenu_2")
        ],
        [
            InlineKeyboardButton("🎯 THIRD VERIFICATION", callback_data="vmenu_3")
        ],
        [
            InlineKeyboardButton("👥 VERIFY LOG CHANNEL", callback_data="vmenu_log_channel")
        ],
        [
            InlineKeyboardButton("‹ BACK", callback_data="admin_settings")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


async def get_step_verify_markup(step: int) -> tuple:
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])
    ord_name = info["ord"]

    status_icon = "✅" if cfg.get("is_active") else "❌"
    
    text = (
        f"🚀 <b><u>{info['title']}:</u></b>\n\n"
        f"<b>• ꜱᴛᴀᴛᴜꜱ:</b> {status_icon} <b>{'ACTIVE' if cfg.get('is_active') else 'DISABLED'}</b>\n"
        f"<b>• ꜱʜᴏʀᴛɴᴇʀ:</b> <code>{cfg.get('shortener_site') or 'Not Set'}</code>\n"
        f"<b>• ᴀᴘɪ ᴋᴇʏ:</b> <code>{cfg.get('shortener_api')[:10] + '...' if cfg.get('shortener_api') and len(cfg.get('shortener_api')) > 10 else (cfg.get('shortener_api') or 'Not Set')}</code>\n"
        f"<b>• ᴛᴜᴛᴏʀɪᴀʟ:</b> {cfg.get('tutorial') or 'Not Set'}\n"
        f"<b>• ᴠᴇʀɪꜰʏ ᴛɪᴍᴇ:</b> <code>{get_readable_time(cfg.get('time', 1200))}</code> (<code>{cfg.get('time', 1200)}s</code>)\n"
        f"<b>• ᴀɴᴛɪ-ʙʏᴘᴀꜱꜱ:</b> <code>{cfg.get('anti_bypass_time', 0)}s</code>\n"
    )

    buttons = [
        [
            InlineKeyboardButton(f"💳 {ord_name} VERIFY SHORTNER", callback_data=f"vact_{step}_shortener")
        ],
        [
            InlineKeyboardButton(f"🍿 {ord_name} VERIFY TUTORIAL", callback_data=f"vact_{step}_tutorial")
        ],
        [
            InlineKeyboardButton(f"⏳ {ord_name} VERIFY TIME", callback_data=f"vact_{step}_time")
        ],
        [
            InlineKeyboardButton(f"🛡 {ord_name} ANTI-BYPASS TIME", callback_data=f"vact_{step}_antibypass")
        ],
        [
            InlineKeyboardButton(f"✍ {ord_name} VERIFY TEXT", callback_data=f"vact_{step}_text")
        ],
        [
            InlineKeyboardButton(f"🖼 {ord_name} VERIFY PIC", callback_data=f"vact_{step}_pic")
        ],
        [
            InlineKeyboardButton(f"👤 TOTAL USER VERIFIED TODAY", callback_data=f"vact_{step}_stats")
        ],
        [
            InlineKeyboardButton(f"{ord_name} VERIFY - {status_icon}", callback_data=f"vtoggle_{step}")
        ],
        [
            InlineKeyboardButton("‹ BACK", callback_data="verify_manage_panel")
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)


# =========================================================================
# 1. Main Verify Management Hub
# =========================================================================

@Client.on_callback_query(filters.regex(r"^verify_manage_panel$"))
async def verify_manage_panel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    AWAITING_VERIFY_INPUT.pop(query.from_user.id, None)
    AWAITING_LOG_CHANNEL_INPUT.pop(query.from_user.id, None)

    text = (
        "🎯 <b><u>TOKEN VERIFICATION:</u></b>\n\n"
        "❝ <b>TOKEN VERIFICATION:</b> A SYSTEM REQUIRING USERS TO WATCH ADS OR SOLVE CAPTCHAS ON EXTERNAL SITES TO UNLOCK BOT ACCESS FOR TIME THAT BOT OWNER SET AND ALSO ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS. ❞\n\n"
        "Select a verification tier or manage log channel below:"
    )

    await query.message.edit_text(
        text=text,
        reply_markup=get_main_verify_markup(),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


# =========================================================================
# 2. Verification Steps Submenus (1, 2, 3)
# =========================================================================

@Client.on_callback_query(filters.regex(r"^vmenu_(\d+)$"))
async def vmenu_step_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    AWAITING_VERIFY_INPUT.pop(query.from_user.id, None)

    text, markup = await get_step_verify_markup(step)
    await query.message.edit_text(
        text=text,
        reply_markup=markup,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


# =========================================================================
# 3. Toggle Status (ON/OFF)
# =========================================================================

@Client.on_callback_query(filters.regex(r"^vtoggle_(\d+)$"))
async def vtoggle_step_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    cfg = await db.get_verify_step_config(step)
    new_status = not cfg.get("is_active", True)
    await db.update_verify_step_config(step, {"is_active": new_status})

    status_str = "ENABLED ✅" if new_status else "DISABLED ❌"
    await query.answer(f"Step {step} verification is now {status_str}!", show_alert=True)

    text, markup = await get_step_verify_markup(step)
    await query.message.edit_text(
        text=text,
        reply_markup=markup,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


# =========================================================================
# 4. Total Verified Today Stats
# =========================================================================

@Client.on_callback_query(filters.regex(r"^vact_(\d+)_stats$"))
async def vact_stats_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    step_count = await db.get_verified_today_count(step)
    total_count = await db.get_verified_today_count()

    info = STEP_NAMES.get(step, STEP_NAMES[1])
    alert_msg = (
        f"📊 {info['ord']} VERIFY TODAY STATS:\n\n"
        f"👤 Step {step} Verified Today: {step_count} Users\n"
        f"🌐 Total All Steps Today: {total_count} Users"
    )
    await query.answer(alert_msg, show_alert=True)


# =========================================================================
# 5. Interactive Actions: Shortener, Tutorial, Time, Anti-Bypass, Text, Pic
# =========================================================================

@Client.on_callback_query(filters.regex(r"^vact_(\d+)_(shortener|tutorial|time|antibypass|text|pic)$"))
async def vact_action_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    action = query.matches[0].group(2)
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])
    ord_name = info["ord"]

    AWAITING_VERIFY_INPUT[query.from_user.id] = {
        "step": step,
        "action": action,
        "prompt_id": query.message.id
    }

    if action == "shortener":
        text = (
            f"💳 <b><u>Set {ord_name} Verify Shortener & API</u></b>\n\n"
            f"<b>Current Site:</b> <code>{cfg.get('shortener_site') or 'Not set'}</code>\n"
            f"<b>Current API:</b> <code>{cfg.get('shortener_api') or 'Not set'}</code>\n\n"
            "📝 <b>Format:</b> Send Shortener Domain and API Key separated by a space.\n\n"
            "<b>Example:</b>\n"
            "<code>shareus.io 1234567890abcdef1234567890abcdef</code>\n\n"
            "<i>Or send single link / domain if API is separated.</i>"
        )
        buttons = [
            [InlineKeyboardButton("🗑️ Reset to Default", callback_data=f"vreset_{step}_shortener")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vmenu_{step}")]
        ]

    elif action == "tutorial":
        text = (
            f"🍿 <b><u>Set {ord_name} Verify Tutorial</u></b>\n\n"
            f"<b>Current Tutorial:</b> {cfg.get('tutorial') or 'Not set'}\n\n"
            "📝 Send the new tutorial link or video URL for this verification step."
        )
        buttons = [
            [InlineKeyboardButton("🗑️ Reset to Default", callback_data=f"vreset_{step}_tutorial")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vmenu_{step}")]
        ]

    elif action == "time":
        current_time = cfg.get('time', 1200)
        text = (
            f"⏳ <b><u>Set {ord_name} Verify Expiration Time</u></b>\n\n"
            f"<b>Current Time:</b> <code>{get_readable_time(current_time)}</code> (<code>{current_time}</code> seconds)\n\n"
            "📝 Send new time in seconds (e.g., <code>1200</code>) or with units like <code>30m</code>, <code>2h</code>, <code>24h</code>, <code>1d</code>.\n\n"
            "Or choose a quick preset below:"
        )
        buttons = [
            [
                InlineKeyboardButton("15 Min", callback_data=f"vtimepreset_{step}_900"),
                InlineKeyboardButton("30 Min", callback_data=f"vtimepreset_{step}_1800"),
                InlineKeyboardButton("1 Hour", callback_data=f"vtimepreset_{step}_3600")
            ],
            [
                InlineKeyboardButton("12 Hours", callback_data=f"vtimepreset_{step}_43200"),
                InlineKeyboardButton("24 Hours", callback_data=f"vtimepreset_{step}_86400")
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vmenu_{step}")]
        ]

    elif action == "antibypass":
        current_ab = cfg.get('anti_bypass_time', 0)
        text = (
            f"🛡 <b><u>Set {ord_name} Anti-Bypass Time</u></b>\n\n"
            f"<b>Current Anti-Bypass Time:</b> <code>{current_ab}</code> seconds\n\n"
            "📝 Send minimum buffer time in seconds (e.g. <code>10</code> or <code>15</code>) to block instant bypass scripts.\n"
            "Send <code>0</code> to disable."
        )
        buttons = [
            [
                InlineKeyboardButton("0s (Off)", callback_data=f"vabpreset_{step}_0"),
                InlineKeyboardButton("10s", callback_data=f"vabpreset_{step}_10"),
                InlineKeyboardButton("15s", callback_data=f"vabpreset_{step}_15")
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vmenu_{step}")]
        ]

    elif action == "text":
        current_txt = cfg.get('text') or script.VERIFICATION_TEXT
        text = (
            f"✍ <b><u>Set {ord_name} Verify Custom Text</u></b>\n\n"
            f"<b>Current Text Preview:</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{current_txt[:350]}...\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            "📝 Send the new verification text message.\n\n"
            "<b>Available Placeholders:</b>\n"
            "• <code>{}</code> or <code>{mention}</code> - User Mention\n"
            "• <code>{time}</code> - Verification Validity Time\n"
            "• <code>{step}</code> - Step Number"
        )
        buttons = [
            [InlineKeyboardButton("🗑️ Reset to Default", callback_data=f"vreset_{step}_text")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vmenu_{step}")]
        ]

    elif action == "pic":
        current_pic = cfg.get('pic') or VERIFY_IMG
        text = (
            f"🖼 <b><u>Set {ord_name} Verify Picture</u></b>\n\n"
            f"<b>Current Picture:</b> <code>{current_pic}</code>\n\n"
            "📝 Send a photo or an image URL (Telegraph/direct link) to display on the verification prompt."
        )
        buttons = [
            [InlineKeyboardButton("🗑️ Reset to Default", callback_data=f"vreset_{step}_pic")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vmenu_{step}")]
        ]

    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


# =========================================================================
# 6. Presets & Resets Callbacks
# =========================================================================

@Client.on_callback_query(filters.regex(r"^vtimepreset_(\d+)_(\d+)$"))
async def vtimepreset_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    time_sec = int(query.matches[0].group(2))
    await db.update_verify_step_config(step, {"time": time_sec})
    AWAITING_VERIFY_INPUT.pop(query.from_user.id, None)

    await query.answer(f"Verification time updated to {get_readable_time(time_sec)}! ✅", show_alert=True)
    text, markup = await get_step_verify_markup(step)
    await query.message.edit_text(text=text, reply_markup=markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"^vabpreset_(\d+)_(\d+)$"))
async def vabpreset_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    ab_sec = int(query.matches[0].group(2))
    await db.update_verify_step_config(step, {"anti_bypass_time": ab_sec})
    AWAITING_VERIFY_INPUT.pop(query.from_user.id, None)

    await query.answer(f"Anti-bypass time updated to {ab_sec}s! ✅", show_alert=True)
    text, markup = await get_step_verify_markup(step)
    await query.message.edit_text(text=text, reply_markup=markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"^vreset_(\d+)_(shortener|tutorial|text|pic)$"))
async def vreset_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    target = query.matches[0].group(2)
    AWAITING_VERIFY_INPUT.pop(query.from_user.id, None)

    if target == "shortener":
        if step == 1:
            site, api = SHORTENER_WEBSITE, SHORTENER_API
        elif step == 2:
            site, api = SHORTENER_WEBSITE2, SHORTENER_API2
        else:
            site, api = SHORTENER_WEBSITE3, SHORTENER_API3
        await db.update_verify_step_config(step, {"shortener_site": site, "shortener_api": api})
        await query.answer("Shortener reset to default! ✅", show_alert=True)

    elif target == "tutorial":
        if step == 1:
            tut = TUTORIAL
        elif step == 2:
            tut = TUTORIAL_2
        else:
            tut = TUTORIAL_3
        await db.update_verify_step_config(step, {"tutorial": tut})
        await query.answer("Tutorial reset to default! ✅", show_alert=True)

    elif target == "text":
        if step == 1:
            txt = script.VERIFICATION_TEXT
        elif step == 2:
            txt = script.SECOND_VERIFICATION_TEXT
        else:
            txt = script.THIRDT_VERIFICATION_TEXT
        await db.update_verify_step_config(step, {"text": txt})
        await query.answer("Text reset to default! ✅", show_alert=True)

    elif target == "pic":
        await db.update_verify_step_config(step, {"pic": VERIFY_IMG})
        await query.answer("Picture reset to default! ✅", show_alert=True)

    text, markup = await get_step_verify_markup(step)
    await query.message.edit_text(text=text, reply_markup=markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)


# =========================================================================
# 7. Log Channel Menu & Handlers
# =========================================================================

@Client.on_callback_query(filters.regex(r"^vmenu_log_channel$"))
async def vmenu_log_channel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    AWAITING_VERIFY_INPUT.pop(query.from_user.id, None)
    AWAITING_LOG_CHANNEL_INPUT.pop(query.from_user.id, None)

    log_channel = await db.get_verify_log_channel()

    status_txt = (
        f"<b>CURRENT VERIFY LOG CHANNEL:</b> <code>{log_channel}</code>"
        if log_channel
        else "<b>YOU DIDN'T ADD ANY VERIFY LOG CHANNEL !</b>"
    )

    text = (
        "👥 <b><u>VERIFY LOG CHANNEL:</u></b>\n\n"
        "❝ <b>WHAT IS VERIFY LOG CHANNEL ??</b>\n"
        "IF USERS COMPLETE VERIFICATION THEN BOT NOTIFIES YOU.\n"
        "IF ANY USER BYPASSES VERIFICATION (PREMIUM) THEN BOT ALSO NOTIFIES YOU WITH DETAILS. ❞\n\n"
        f"{status_txt}"
    )

    buttons = [
        [
            InlineKeyboardButton("SET CHANNEL", callback_data="vlog_set")
        ],
        [
            InlineKeyboardButton("DELETE CHANNEL", callback_data="vlog_del")
        ],
        [
            InlineKeyboardButton("‹ BACK", callback_data="verify_manage_panel")
        ]
    ]

    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vlog_set$"))
async def vlog_set_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    AWAITING_LOG_CHANNEL_INPUT[query.from_user.id] = query.message.id

    text = (
        "👥 <b><u>Set Verify Log Channel</u></b>\n\n"
        "📝 Please send the <b>Channel ID</b> (e.g. <code>-1001234567890</code>) or forward any message from your Log Channel.\n\n"
        "⚠️ <i>Make sure this Bot is added as an Admin in the channel with full message posting rights!</i>"
    )
    buttons = [
        [InlineKeyboardButton("❌ Cancel", callback_data="vmenu_log_channel")]
    ]
    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex(r"^vlog_del$"))
async def vlog_del_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    await db.delete_verify_log_channel()
    await query.answer("SUCCESSFULLY DELETED LOG CHANNEL ✅", show_alert=True)

    # Refresh channel view
    text = (
        "👥 <b><u>VERIFY LOG CHANNEL:</u></b>\n\n"
        "❝ <b>WHAT IS VERIFY LOG CHANNEL ??</b>\n"
        "IF USERS COMPLETE VERIFICATION THEN BOT NOTIFIES YOU.\n"
        "IF ANY USER BYPASSES VERIFICATION (PREMIUM) THEN BOT ALSO NOTIFIES YOU WITH DETAILS. ❞\n\n"
        "<b>YOU DIDN'T ADD ANY VERIFY LOG CHANNEL !</b>"
    )
    buttons = [
        [InlineKeyboardButton("SET CHANNEL", callback_data="vlog_set")],
        [InlineKeyboardButton("DELETE CHANNEL", callback_data="vlog_del")],
        [InlineKeyboardButton("‹ BACK", callback_data="verify_manage_panel")]
    ]
    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


# =========================================================================
# 8. Admin Input Handler for Verification Settings
# =========================================================================

def parse_time_input(text_val: str) -> int:
    text_val = text_val.strip().lower()
    if text_val.endswith("s"):
        return int(text_val[:-1])
    if text_val.endswith("m"):
        return int(text_val[:-1]) * 60
    if text_val.endswith("h"):
        return int(text_val[:-1]) * 3600
    if text_val.endswith("d"):
        return int(text_val[:-1]) * 86400
    return int(text_val)


@Client.on_message(filters.private & ~filters.command(["start", "admin", "settings", "cancel"]))
async def verify_admin_input_handler(client: Client, message: Message):
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        return

    # Check Log Channel Input
    if admin_id in AWAITING_LOG_CHANNEL_INPUT:
        AWAITING_LOG_CHANNEL_INPUT.pop(admin_id, None)
        target_channel_id = None

        if message.forward_from_chat:
            target_channel_id = message.forward_from_chat.id
        elif message.text:
            cleaned = message.text.strip()
            try:
                target_channel_id = int(cleaned)
            except ValueError:
                pass

        if not target_channel_id:
            return await message.reply_text("❌ <b>Invalid Channel ID!</b> Please send a valid numeric ID like <code>-1001234567890</code>.")

        # Test bot admin rights in channel
        try:
            chat = await client.get_chat(target_channel_id)
            test_msg = await client.send_message(
                target_channel_id,
                f"✅ <b>Verify Log Channel Configured Successfully!</b>\nAdded by: {message.from_user.mention}"
            )
            await db.set_verify_log_channel(target_channel_id)
            btn = [[InlineKeyboardButton("« Return to Verify Panel", callback_data="vmenu_log_channel")]]
            return await message.reply_text(
                f"✅ <b>Verify Log Channel Set Successfully!</b>\n\n"
                f"📢 <b>Channel:</b> <code>{chat.title}</code> (<code>{target_channel_id}</code>)",
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except Exception as e:
            return await message.reply_text(
                f"❌ <b>Failed to configure Log Channel!</b>\n\n"
                f"<b>Error:</b> <code>{str(e)}</code>\n\n"
                "<i>Please ensure the bot is added to the channel as an Administrator with 'Post Messages' permission.</i>"
            )

    # Check Step Config Input
    if admin_id in AWAITING_VERIFY_INPUT:
        ctx = AWAITING_VERIFY_INPUT.pop(admin_id, None)
        if not ctx:
            return

        step = ctx["step"]
        action = ctx["action"]
        info = STEP_NAMES.get(step, STEP_NAMES[1])
        ord_name = info["ord"]

        if action == "shortener":
            text_val = (message.text or "").strip()
            parts = text_val.split(None, 1)
            if len(parts) >= 2:
                site = parts[0].strip().replace("https://", "").replace("http://", "").rstrip("/")
                api = parts[1].strip()
            elif ":" in text_val:
                site, api = text_val.split(":", 1)
                site = site.strip().replace("https://", "").replace("http://", "").rstrip("/")
                api = api.strip()
            else:
                return await message.reply_text(
                    "❌ <b>Invalid Format!</b>\nPlease provide both domain and API key separated by space.\nExample: <code>shareus.io 123456789abcdef</code>"
                )

            await db.update_verify_step_config(step, {"shortener_site": site, "shortener_api": api})
            btn = [[InlineKeyboardButton(f"« Return to {ord_name} Verify", callback_data=f"vmenu_{step}")]]
            return await message.reply_text(
                f"✅ <b>{ord_name} Verify Shortener Updated!</b>\n\n"
                f"• <b>Domain:</b> <code>{site}</code>\n"
                f"• <b>API:</b> <code>{api[:8]}...</code>",
                reply_markup=InlineKeyboardMarkup(btn)
            )

        elif action == "tutorial":
            text_val = (message.text or "").strip()
            if not text_val.startswith(("http://", "https://", "t.me/")):
                return await message.reply_text("❌ <b>Invalid Link!</b> Please send a valid HTTP/HTTPS or Telegram link.")
            await db.update_verify_step_config(step, {"tutorial": text_val})
            btn = [[InlineKeyboardButton(f"« Return to {ord_name} Verify", callback_data=f"vmenu_{step}")]]
            return await message.reply_text(
                f"✅ <b>{ord_name} Verify Tutorial Link Updated!</b>\n\n"
                f"• <b>Link:</b> {text_val}",
                reply_markup=InlineKeyboardMarkup(btn)
            )

        elif action == "time":
            text_val = (message.text or "").strip()
            try:
                seconds = parse_time_input(text_val)
                if seconds <= 0:
                    raise ValueError
            except Exception:
                return await message.reply_text("❌ <b>Invalid Time!</b> Please send positive seconds or format like <code>30m</code>, <code>2h</code>, <code>24h</code>.")

            await db.update_verify_step_config(step, {"time": seconds})
            btn = [[InlineKeyboardButton(f"« Return to {ord_name} Verify", callback_data=f"vmenu_{step}")]]
            return await message.reply_text(
                f"✅ <b>{ord_name} Verify Time Updated!</b>\n\n"
                f"• <b>Validity:</b> <code>{get_readable_time(seconds)}</code> (<code>{seconds}s</code>)",
                reply_markup=InlineKeyboardMarkup(btn)
            )

        elif action == "antibypass":
            text_val = (message.text or "").strip()
            try:
                seconds = int(text_val)
                if seconds < 0:
                    raise ValueError
            except Exception:
                return await message.reply_text("❌ <b>Invalid Seconds!</b> Please send a non-negative number like <code>10</code> or <code>0</code>.")

            await db.update_verify_step_config(step, {"anti_bypass_time": seconds})
            btn = [[InlineKeyboardButton(f"« Return to {ord_name} Verify", callback_data=f"vmenu_{step}")]]
            return await message.reply_text(
                f"✅ <b>{ord_name} Anti-Bypass Time Updated!</b>\n\n"
                f"• <b>Buffer:</b> <code>{seconds} seconds</code>",
                reply_markup=InlineKeyboardMarkup(btn)
            )

        elif action == "text":
            raw_text = message.text.html if hasattr(message.text, 'html') else message.text
            if not raw_text:
                return await message.reply_text("❌ <b>Please send text content!</b>")
            await db.update_verify_step_config(step, {"text": raw_text})
            btn = [[InlineKeyboardButton(f"« Return to {ord_name} Verify", callback_data=f"vmenu_{step}")]]
            return await message.reply_text(
                f"✅ <b>{ord_name} Verify Custom Text Updated!</b>",
                reply_markup=InlineKeyboardMarkup(btn)
            )

        elif action == "pic":
            pic_url = None
            if message.photo:
                pic_url = message.photo.file_id
            elif message.text and message.text.startswith(("http://", "https://")):
                pic_url = message.text.strip()

            if not pic_url:
                return await message.reply_text("❌ <b>Please send a photo or a valid image URL!</b>")

            await db.update_verify_step_config(step, {"pic": pic_url})
            btn = [[InlineKeyboardButton(f"« Return to {ord_name} Verify", callback_data=f"vmenu_{step}")]]
            return await message.reply_text(
                f"✅ <b>{ord_name} Verify Picture Updated!</b>",
                reply_markup=InlineKeyboardMarkup(btn)
            )
