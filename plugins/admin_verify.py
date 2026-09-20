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
    1: {"name": "FIRST", "title": "FIRST TOKEN VERIFICATION:", "ord": "FIRST"},
    2: {"name": "SECOND", "title": "SECOND TOKEN VERIFICATION:", "ord": "SECOND"},
    3: {"name": "THIRD", "title": "THIRD TOKEN VERIFICATION:", "ord": "THIRD"},
}


def is_admin(user_id: int) -> bool:
    try:
        uid = int(user_id)
        return uid in ADMINS or str(uid) in [str(a) for a in ADMINS]
    except Exception:
        return False


def format_verify_time_display(seconds: int) -> str:
    try:
        sec = int(seconds)
    except Exception:
        sec = 1200
    if sec >= 86400 and sec % 86400 == 0:
        days = sec // 86400
        mins = sec // 60
        return f"{days} Day{'s' if days > 1 else ''} ({mins} Minutes)"
    elif sec >= 3600 and sec % 3600 == 0:
        hours = sec // 3600
        mins = sec // 60
        return f"{hours} Hour{'s' if hours > 1 else ''} ({mins} Minutes)"
    elif sec >= 60:
        mins = sec // 60
        return f"{mins}m ({sec}s)"
    else:
        return f"{sec} Seconds"


# =========================================================================
# 1. Main Verify Management Hub Markup
# =========================================================================

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


# =========================================================================
# 2. Step Hub Markup (Exact matches from video)
# =========================================================================

async def get_step_verify_markup(step: int) -> tuple:
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])
    ord_name = info["ord"]

    status_icon = "✅" if cfg.get("is_active", True) else "❌"
    
    text = f"🎯 <b>{info['title']}</b>"

    buttons = [
        [
            InlineKeyboardButton(f"💳 {ord_name} VERIFY SHORTNER", callback_data=f"vsub_{step}_shortener")
        ],
        [
            InlineKeyboardButton(f"🍿 {ord_name} VERIFY TUTORIAL", callback_data=f"vsub_{step}_tutorial")
        ],
        [
            InlineKeyboardButton(f"⏳ {ord_name} VERIFY TIME", callback_data=f"vsub_{step}_time")
        ],
        [
            InlineKeyboardButton(f"🛡 {ord_name} ANTI-BYPASS TIME", callback_data=f"vsub_{step}_antibypass")
        ],
        [
            InlineKeyboardButton(f"✍ {ord_name} VERIFY TEXT", callback_data=f"vsub_{step}_text")
        ],
        [
            InlineKeyboardButton(f"🖼 {ord_name} VERIFY PIC", callback_data=f"vsub_{step}_pic")
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
# 3. Main Callbacks
# =========================================================================

@Client.on_callback_query(filters.regex(r"^verify_manage_panel$"))
async def verify_manage_panel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    AWAITING_VERIFY_INPUT.pop(query.from_user.id, None)
    AWAITING_LOG_CHANNEL_INPUT.pop(query.from_user.id, None)

    text = (
        "🎯 <b>TOKEN VERIFICATION:</b>\n\n"
        "❝ <b>TOKEN VERIFICATION:</b> A SYSTEM REQUIRING USERS TO WATCH ADS OR SOLVE CAPTCHAS ON EXTERNAL SITES TO UNLOCK BOT ACCESS FOR TIME THAT BOT OWNER SET AND ALSO ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS. ❞"
    )

    await query.message.edit_text(
        text=text,
        reply_markup=get_main_verify_markup(),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


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


@Client.on_callback_query(filters.regex(r"^vtoggle_(\d+)$"))
async def vtoggle_step_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    cfg = await db.get_verify_step_config(step)
    new_status = not cfg.get("is_active", True)
    await db.update_verify_step_config(step, {"is_active": new_status})

    status_str = "ENABLED ✅" if new_status else "DISABLED ❌"
    await query.answer(f"Step {step} verification is now {status_str}!", show_alert=False)

    text, markup = await get_step_verify_markup(step)
    await query.message.edit_text(
        text=text,
        reply_markup=markup,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vact_(\d+)_stats$"))
async def vact_stats_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    step_count = await db.get_verified_today_count(step)
    total_count = await db.get_verified_today_count()
    info = STEP_NAMES.get(step, STEP_NAMES[1])

    alert_msg = f"👤 TOTAL USERS VERIFIED TODAY:\n\n• {info['ord']} Verify: {step_count}\n• All Steps Combined: {total_count}"
    await query.answer(alert_msg, show_alert=True)


# =========================================================================
# 4. Step Sub-Screens (Shortener, Tutorial, Time, Anti-Bypass, Text, Pic)
# =========================================================================

# --- 4.1 Shortener Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_shortener$"))
async def vsub_shortener_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])
    ord_name = info["ord"]

    url_val = cfg.get("shortener_site") or "Not Set"
    api_val = cfg.get("shortener_api") or "Not Set"

    text = (
        f"💳 <b>{ord_name} VERIFY SHORTNER:</b>\n\n"
        "❝ <b>LINK SHORTENER:</b> A TOOL THAT CONVERTS FILE LINKS INTO MONETIZED URLS, ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS. ❞\n\n"
        f"<b>URL</b> - {url_val}\n"
        f"<b>API</b> - {api_val}"
    )

    buttons = [
        [InlineKeyboardButton("SET SHORTLINK", callback_data=f"vprompt_{step}_shortener")],
        [InlineKeyboardButton("DELETE SHORTLINK", callback_data=f"vdel_{step}_shortener")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vdel_(\d+)_shortener$"))
async def vdel_shortener_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    await db.update_verify_step_config(step, {
        "shortener_site": "",
        "shortener_api": ""
    })
    await query.answer("SUCCESSFULLY DELETED SHORTLINK ✅", show_alert=True)
    await vsub_shortener_cb(client, query)


# --- 4.2 Tutorial Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_tutorial$"))
async def vsub_tutorial_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])
    ord_name = info["ord"]

    link_val = cfg.get("tutorial") or "Not Set"

    text = (
        f"🍿 <b>{ord_name} VERIFY TUTORIAL:</b>\n\n"
        "❝ <b>TUTORIAL LINK:</b> THE PROCESS VIDEO OF OPENING LINK OF SHORTER. LINK OF VIDEO OR CHANNEL WHERE VIDEO IS UPLOADED. VIDEO MEANS VIDEO OF HOW TO OPEN LINK. ❞\n\n"
        f"<b>LINK</b> - {link_val}"
    )

    buttons = [
        [InlineKeyboardButton("SET TUTORIAL", callback_data=f"vprompt_{step}_tutorial")],
        [InlineKeyboardButton("DELETE TUTORIAL", callback_data=f"vdel_{step}_tutorial")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vdel_(\d+)_tutorial$"))
async def vdel_tutorial_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    await db.update_verify_step_config(step, {"tutorial": ""})
    await query.answer("SUCCESSFULLY DELETED TUTORIAL ✅", show_alert=True)
    await vsub_tutorial_cb(client, query)


# --- 4.3 Verify Time Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_time$"))
async def vsub_time_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])
    ord_name = info["ord"]

    current_sec = cfg.get("time", 1200 if step == 1 else (TWO_VERIFY_GAP if step == 2 else THREE_VERIFY_GAP))
    time_display = format_verify_time_display(current_sec)

    text = (
        f"⏳ <b>{ord_name} VERIFY TIME:</b>\n\n"
        "❝ <b>VERIFICATION TIME:</b> DURATION FOR WHICH USER GETS BOT ACCESS AFTER COMPLETING ACCESS TOKEN. ❞\n\n"
        f"<b>TIME</b> - {time_display}"
    )

    buttons = [
        [InlineKeyboardButton("SET VERIFY TIME", callback_data=f"vprompt_{step}_time")],
        [InlineKeyboardButton("RESET TIME", callback_data=f"vdel_{step}_time")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vdel_(\d+)_time$"))
async def vdel_time_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    default_time = 1200 if step == 1 else (TWO_VERIFY_GAP if step == 2 else THREE_VERIFY_GAP)
    await db.update_verify_step_config(step, {"time": default_time})
    await query.answer("SUCCESSFULLY RESET VERIFY TIME ✅", show_alert=True)
    await vsub_time_cb(client, query)


# --- 4.4 Anti-Bypass Time Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_antibypass$"))
async def vsub_antibypass_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])
    ord_name = info["ord"]

    antibypass_sec = cfg.get("anti_bypass_time", 12)

    text = (
        f"🛡 <b>{ord_name} ANTI-BYPASS TIME:</b>\n\n"
        "❝ <b>ANTI-BYPASS PROTECTION:</b> Sets the minimum time (in seconds) a user must spend before verification is accepted. Shortener bypass bots that resolve instantly will be detected and blocked! ❞\n\n"
        f"<b>MINIMUM TIME</b> - {antibypass_sec} Seconds\n"
        "(Default: 12s)"
    )

    buttons = [
        [InlineKeyboardButton("SET BYPASS TIME", callback_data=f"vprompt_{step}_antibypass")],
        [InlineKeyboardButton("RESET BYPASS TIME (12s)", callback_data=f"vdel_{step}_antibypass")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vdel_(\d+)_antibypass$"))
async def vdel_antibypass_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    await db.update_verify_step_config(step, {"anti_bypass_time": 12})
    await query.answer("SUCCESSFULLY RESET ANTI-BYPASS TIME ✅", show_alert=True)
    await vsub_antibypass_cb(client, query)


# --- 4.5 Verify Text Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_text$"))
async def vsub_text_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])
    ord_name = info["ord"]

    has_custom_text = bool(cfg.get("text"))
    status_text = "CUSTOM TEXT ✅" if has_custom_text else "DEFAULT TEXT ✅"

    text = (
        f"✍ <b>{ord_name} VERIFY TEXT:</b>\n\n"
        "❝ <b>VERIFY TEXT:</b> CUSTOM MESSAGE SENT TO USERS PROMPTING THEM TO VERIFY AND UNLOCK BOT ACCESS. ❞\n\n"
        f"<b>STATUS:</b> {status_text}"
    )

    buttons = [
        [InlineKeyboardButton("SET VERIFY TEXT", callback_data=f"vprompt_{step}_text")],
        [InlineKeyboardButton("SEE VERIFY TEXT", callback_data=f"vsee_{step}_text")],
        [InlineKeyboardButton("RESET VERIFY TEXT", callback_data=f"vdel_{step}_text")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vsee_(\d+)_text$"))
async def vsee_text_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])

    current_text = cfg.get("text")
    if not current_text:
        if step == 3:
            current_text = script.THIRDT_VERIFICATION_TEXT
        elif step == 2:
            current_text = script.SECOND_VERIFICATION_TEXT
        else:
            current_text = script.VERIFICATION_TEXT

    preview_msg = f"📝 <b><u>{info['ord']} Verify Text Preview:</u></b>\n\n{current_text}"
    await query.message.reply_text(preview_msg, parse_mode=enums.ParseMode.HTML)
    await query.answer("Sent preview above 👆", show_alert=False)


@Client.on_callback_query(filters.regex(r"^vdel_(\d+)_text$"))
async def vdel_text_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    await db.update_verify_step_config(step, {"text": ""})
    await query.answer("SUCCESSFULLY RESET VERIFY TEXT ✅", show_alert=True)
    await vsub_text_cb(client, query)


# --- 4.6 Verify Pic Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_pic$"))
async def vsub_pic_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])
    ord_name = info["ord"]

    pic_val = cfg.get("pic")
    if pic_val and pic_val != "None":
        photo_status = "ATTACHED ✅"
    else:
        photo_status = "NOT SET (TEXT ONLY) ❌"

    text = (
        f"🖼 <b>{ord_name} VERIFY PIC:</b>\n\n"
        "❝ <b>ATTACH A PHOTO WITH YOUR VERIFICATION PROMPT MESSAGE TO MAKE IT MORE ATTRACTIVE.</b> ❞\n\n"
        f"<b>PHOTO STATUS:</b> {photo_status}"
    )

    buttons = [
        [InlineKeyboardButton("SET VERIFY PIC", callback_data=f"vprompt_{step}_pic")],
        [InlineKeyboardButton("DELETE VERIFY PIC", callback_data=f"vdel_{step}_pic")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vdel_(\d+)_pic$"))
async def vdel_pic_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    await db.update_verify_step_config(step, {"pic": ""})
    await query.answer("SUCCESSFULLY DELETED VERIFY PIC ✅", show_alert=True)
    await vsub_pic_cb(client, query)


# =========================================================================
# 5. Interactive Prompts For Inputs
# =========================================================================

@Client.on_callback_query(filters.regex(r"^vprompt_(\d+)_(shortener|tutorial|time|antibypass|text|pic)$"))
async def vprompt_input_cb(client: Client, query: CallbackQuery):
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
            f"<b>Current Site:</b> <code>{cfg.get('shortener_site') or 'Not Set'}</code>\n"
            f"<b>Current API:</b> <code>{cfg.get('shortener_api') or 'Not Set'}</code>\n\n"
            "📝 <b>Format:</b> Send Shortener Domain and API Key separated by a space.\n\n"
            "<b>Example:</b>\n"
            "<code>shareus.io 1234567890abcdef1234567890abcdef</code>\n\n"
            "<i>Or send single link / domain if API is separated.</i>"
        )
        buttons = [
            [InlineKeyboardButton("🔄 Reset to Default", callback_data=f"vdel_{step}_shortener")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vsub_{step}_shortener")]
        ]

    elif action == "tutorial":
        text = (
            f"🍿 <b><u>Set {ord_name} Verify Tutorial</u></b>\n\n"
            f"<b>Current Tutorial:</b> {cfg.get('tutorial') or 'Not Set'}\n\n"
            "📝 Send the new tutorial link or video URL for this verification step."
        )
        buttons = [
            [InlineKeyboardButton("🔄 Reset to Default", callback_data=f"vdel_{step}_tutorial")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vsub_{step}_tutorial")]
        ]

    elif action == "time":
        current_time_str = format_verify_time_display(cfg.get('time', 1200))
        text = (
            f"⏳ <b><u>Set {ord_name} Verify Time</u></b>\n\n"
            f"<b>Current Time:</b> {current_time_str}\n\n"
            "📝 Send duration in seconds (e.g. <code>1200</code> for 20m, <code>86400</code> for 24h) or choose a preset below:"
        )
        buttons = [
            [
                InlineKeyboardButton("15 Min", callback_data=f"vsettime_{step}_900"),
                InlineKeyboardButton("30 Min", callback_data=f"vsettime_{step}_1800"),
            ],
            [
                InlineKeyboardButton("1 Hour", callback_data=f"vsettime_{step}_3600"),
                InlineKeyboardButton("12 Hours", callback_data=f"vsettime_{step}_43200"),
                InlineKeyboardButton("24 Hours", callback_data=f"vsettime_{step}_86400"),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vsub_{step}_time")]
        ]

    elif action == "antibypass":
        text = (
            f"🛡 <b><u>Set {ord_name} Anti-Bypass Time</u></b>\n\n"
            f"<b>Current Minimum Time:</b> {cfg.get('anti_bypass_time', 12)} Seconds\n\n"
            "📝 Send the minimum required time in seconds (e.g. <code>12</code> or <code>15</code>) that user must spend before submitting verification token."
        )
        buttons = [
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vsub_{step}_antibypass")]
        ]

    elif action == "text":
        text = (
            f"✍ <b><u>Set {ord_name} Verify Prompt Text</u></b>\n\n"
            "📝 Send the custom text message to display when prompting users to verify.\n\n"
            "You can use formatting tags (<b>bold</b>, <i>italic</i>) and <code>{mention}</code> placeholder."
        )
        buttons = [
            [InlineKeyboardButton("🔄 Reset to Default", callback_data=f"vdel_{step}_text")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vsub_{step}_text")]
        ]

    elif action == "pic":
        text = (
            f"🖼 <b><u>Set {ord_name} Verify Picture</u></b>\n\n"
            "📝 Send a photo directly, or send an image URL (telegra.ph / direct link) to attach to verification messages."
        )
        buttons = [
            [InlineKeyboardButton("❌ Cancel", callback_data=f"vsub_{step}_pic")]
        ]
    else:
        return

    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vsettime_(\d+)_(\d+)$"))
async def vsettime_preset_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    seconds = int(query.matches[0].group(2))
    await db.update_verify_step_config(step, {"time": seconds})
    await query.answer(f"Verify time updated to {format_verify_time_display(seconds)} ✅", show_alert=True)
    await vsub_time_cb(client, query)


# =========================================================================
# 6. Verify Log Channel Menu & Handlers (Exact match from video)
# =========================================================================

async def get_log_channel_markup() -> tuple:
    chnl_id = await db.get_verify_log_channel()
    if chnl_id:
        status_line = f"<b>CURRENT VERIFY LOG CHANNEL:</b> <code>{chnl_id}</code>"
    else:
        status_line = "<b>YOU DIDN'T ADD ANY VERIFY LOG CHANNEL !</b>"

    text = (
        "👥 <b>VERIFY LOG CHANNEL:</b>\n\n"
        "❝ <b>WHAT IS VERIFY LOG CHANNEL ??</b>\n"
        "IF USERS COMPLETE VERIFICATION THEN BOT NOTIFIES YOU.\n"
        "IF ANY USER BYPASSES VERIFICATION (PREMIUM) THEN BOT ALSO NOTIFIES YOU WITH DETAILS. ❞\n\n"
        f"{status_line}"
    )

    buttons = [
        [InlineKeyboardButton("SET CHANNEL", callback_data="vact_set_log_channel")],
        [InlineKeyboardButton("DELETE CHANNEL", callback_data="vact_del_log_channel")],
        [InlineKeyboardButton("‹ BACK", callback_data="verify_manage_panel")]
    ]
    return text, InlineKeyboardMarkup(buttons)


@Client.on_callback_query(filters.regex(r"^vmenu_log_channel$"))
async def vmenu_log_channel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    AWAITING_LOG_CHANNEL_INPUT.pop(query.from_user.id, None)
    text, markup = await get_log_channel_markup()
    await query.message.edit_text(
        text=text,
        reply_markup=markup,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vact_del_log_channel$"))
async def vact_del_log_channel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    await db.set_verify_log_channel(None)
    await query.answer("SUCCESSFULLY DELETED LOG CHANNEL ✅", show_alert=True)
    text, markup = await get_log_channel_markup()
    await query.message.edit_text(
        text=text,
        reply_markup=markup,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^vact_set_log_channel$"))
async def vact_set_log_channel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    AWAITING_LOG_CHANNEL_INPUT[query.from_user.id] = query.message.id

    text = (
        "👥 <b><u>Set Verify Log Channel</u></b>\n\n"
        "📝 Send the Channel ID (e.g. <code>-1001234567890</code>) or forward any message from the channel.\n\n"
        "<i>Make sure the bot is added as an Admin in the channel!</i>"
    )
    buttons = [
        [InlineKeyboardButton("❌ Cancel", callback_data="vmenu_log_channel")]
    ]
    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


# =========================================================================
# 7. Incoming Message Listener for Interactive Inputs
# =========================================================================

@Client.on_message(filters.private & ~filters.command(["start", "admin", "adminpanel", "settings"]))
async def verify_settings_input_listener(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    # 1. Log Channel input
    if user_id in AWAITING_LOG_CHANNEL_INPUT:
        prompt_id = AWAITING_LOG_CHANNEL_INPUT.pop(user_id)
        channel_id = None

        if message.forward_from_chat:
            channel_id = message.forward_from_chat.id
        elif message.text:
            text_cleaned = message.text.strip()
            try:
                channel_id = int(text_cleaned)
            except ValueError:
                pass

        if not channel_id:
            await message.reply_text("❌ Invalid Channel ID or Forward. Please send a valid channel ID like <code>-1001234567890</code>.")
            return

        try:
            chat = await client.get_chat(channel_id)
            me = await client.get_me()
            member = await chat.get_member(me.id)
            if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return await message.reply_text("❌ The bot is not an admin in that channel! Please make the bot an admin and try again.")
        except Exception as e:
            return await message.reply_text(f"❌ Error accessing channel: <code>{e}</code>\nMake sure the bot is added as an admin!")

        await db.set_verify_log_channel(channel_id)
        await message.reply_text(
            f"✅ <b>Verify Log Channel Set Successfully!</b>\n\n<b>Title:</b> {chat.title}\n<b>ID:</b> <code>{channel_id}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK TO VERIFY MENU", callback_data="vmenu_log_channel")]])
        )
        return

    # 2. Verification Step inputs
    if user_id in AWAITING_VERIFY_INPUT:
        state = AWAITING_VERIFY_INPUT.pop(user_id)
        step = state["step"]
        action = state["action"]
        info = STEP_NAMES.get(step, STEP_NAMES[1])
        ord_name = info["ord"]

        if action == "shortener":
            text = message.text.strip() if message.text else ""
            parts = text.split()
            if len(parts) >= 2:
                site = parts[0].replace("https://", "").replace("http://", "").rstrip("/")
                api = parts[1]
            elif len(parts) == 1:
                site = parts[0].replace("https://", "").replace("http://", "").rstrip("/")
                api = ""
            else:
                return await message.reply_text("❌ Invalid format. Please send domain and API key separated by a space.")

            update_data = {"shortener_site": site}
            if api:
                update_data["shortener_api"] = api
            await db.update_verify_step_config(step, update_data)
            await message.reply_text(
                f"✅ <b>{ord_name} Verify Shortener Updated!</b>\n\n<b>Site:</b> <code>{site}</code>\n<b>API:</b> <code>{api or 'Unchanged'}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"‹ BACK TO {ord_name} VERIFY", callback_data=f"vsub_{step}_shortener")]])
            )

        elif action == "tutorial":
            tutorial_url = message.text.strip() if message.text else ""
            if not tutorial_url.startswith("http"):
                return await message.reply_text("❌ Please send a valid HTTP/HTTPS URL for the tutorial.")
            await db.update_verify_step_config(step, {"tutorial": tutorial_url})
            await message.reply_text(
                f"✅ <b>{ord_name} Verify Tutorial Updated!</b>\n\n<b>URL:</b> {tutorial_url}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"‹ BACK TO {ord_name} VERIFY", callback_data=f"vsub_{step}_tutorial")]])
            )

        elif action == "time":
            try:
                seconds = int(message.text.strip())
                if seconds <= 0:
                    raise ValueError()
            except Exception:
                return await message.reply_text("❌ Please enter a valid positive number in seconds (e.g. <code>1200</code> for 20m, <code>86400</code> for 24h).")

            await db.update_verify_step_config(step, {"time": seconds})
            await message.reply_text(
                f"✅ <b>{ord_name} Verify Time Updated to:</b> <code>{format_verify_time_display(seconds)}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"‹ BACK TO {ord_name} VERIFY", callback_data=f"vsub_{step}_time")]])
            )

        elif action == "antibypass":
            try:
                seconds = int(message.text.strip())
                if seconds < 0:
                    raise ValueError()
            except Exception:
                return await message.reply_text("❌ Please enter a valid number of seconds (e.g. <code>12</code>).")

            await db.update_verify_step_config(step, {"anti_bypass_time": seconds})
            await message.reply_text(
                f"✅ <b>{ord_name} Anti-Bypass Time Set to:</b> <code>{seconds}s</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"‹ BACK TO {ord_name} VERIFY", callback_data=f"vsub_{step}_antibypass")]])
            )

        elif action == "text":
            raw_text = message.text.html if hasattr(message.text, 'html') and message.text.html else (message.text or "")
            if not raw_text:
                return await message.reply_text("❌ Please send text message content.")
            await db.update_verify_step_config(step, {"text": raw_text})
            await message.reply_text(
                f"✅ <b>{ord_name} Verify Text Updated!</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"‹ BACK TO {ord_name} VERIFY", callback_data=f"vsub_{step}_text")]])
            )

        elif action == "pic":
            pic_url = ""
            if message.photo:
                pic_url = message.photo.file_id
            elif message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
                pic_url = message.text.strip()
            else:
                return await message.reply_text("❌ Please send a photo directly or provide an image URL.")

            await db.update_verify_step_config(step, {"pic": pic_url})
            await message.reply_text(
                f"✅ <b>{ord_name} Verify Picture Updated!</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"‹ BACK TO {ord_name} VERIFY", callback_data=f"vsub_{step}_pic")]])
            )
