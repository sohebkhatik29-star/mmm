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
from info import (
    ADMINS, LOG_VR_CHANNEL, SHORTENER_WEBSITE, SHORTENER_API, TUTORIAL,
    SHORTENER_WEBSITE2, SHORTENER_API2, TUTORIAL_2, SHORTENER_WEBSITE3,
    SHORTENER_API3, TUTORIAL_3, TWO_VERIFY_GAP, THREE_VERIFY_GAP,
    VERIFY_IMG, IS_VERIFY
)
from utils import get_readable_time
from Script import script

logger = logging.getLogger(__name__)

# State tracking for interactive admin inputs
# AWAITING_INPUT[user_id] = {"type": str, "step": int, "prompt_msg_id": int, "temp_data": dict}
AWAITING_INPUT = {}

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
        return f"{mins} Minutes ({sec}s)"
    else:
        return f"{sec} Seconds"


def parse_time_to_seconds(text_val: str) -> int:
    text_val = text_val.strip().lower()
    if text_val.endswith("d") or "day" in text_val:
        num = re.findall(r"\d+", text_val)
        return int(num[0]) * 86400 if num else 86400
    if text_val.endswith("h") or "hour" in text_val or "hr" in text_val:
        num = re.findall(r"\d+", text_val)
        return int(num[0]) * 3600 if num else 3600
    if text_val.endswith("m") or "min" in text_val:
        num = re.findall(r"\d+", text_val)
        return int(num[0]) * 60 if num else 60
    if text_val.endswith("s") or "sec" in text_val:
        num = re.findall(r"\d+", text_val)
        return int(num[0]) if num else 60
    num = re.findall(r"\d+", text_val)
    return int(num[0]) if num else 86400


def clean_domain(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = cleaned.replace("https://", "").replace("http://", "")
    if "/" in cleaned:
        cleaned = cleaned.split("/")[0]
    return cleaned.strip()


async def safe_delete(client: Client, chat_id: int, message_id: int):
    if not message_id:
        return
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=[message_id])
    except Exception:
        pass


# =========================================================================
# 1. Main Verify Management Hub
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


@Client.on_callback_query(filters.regex(r"^verify_manage_panel$"))
async def verify_manage_panel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    AWAITING_INPUT.pop(query.from_user.id, None)

    text = (
        "🎯 <b>TOKEN VERIFICATION:</b>\n\n"
        "❝ <b>TOKEN VERIFICATION:</b> A SYSTEM REQUIRING USERS TO WATCH ADS OR SOLVE CAPTCHAS ON EXTERNAL SITES TO UNLOCK BOT ACCESS FOR TIME THAT BOT OWNER SET AND ALSO ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS. ❞"
    )

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=get_main_verify_markup(),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
            text=text,
            reply_markup=get_main_verify_markup(),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )


# =========================================================================
# 2. Step Hub (FIRST / SECOND / THIRD TOKEN VERIFICATION:)
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


@Client.on_callback_query(filters.regex(r"^vmenu_(\d+)$"))
async def vmenu_step_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    AWAITING_INPUT.pop(query.from_user.id, None)

    text, markup = await get_step_verify_markup(step)
    try:
        await query.message.edit_text(
            text=text,
            reply_markup=markup,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
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
    try:
        await query.message.edit_text(
            text=text,
            reply_markup=markup,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        pass


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
# 3. Step Sub-Screens
# =========================================================================

# --- 3.1 Shortener Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_shortener$"))
async def vsub_shortener_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    AWAITING_INPUT.pop(query.from_user.id, None)
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
        [InlineKeyboardButton("SET SHORTLINK", callback_data=f"vflow_{step}_shortener_url")],
        [InlineKeyboardButton("DELETE SHORTLINK", callback_data=f"vdel_{step}_shortener")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
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


# --- 3.2 Tutorial Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_tutorial$"))
async def vsub_tutorial_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    AWAITING_INPUT.pop(query.from_user.id, None)
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
        [InlineKeyboardButton("SET TUTORIAL", callback_data=f"vflow_{step}_tutorial")],
        [InlineKeyboardButton("DELETE TUTORIAL", callback_data=f"vdel_{step}_tutorial")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
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


# --- 3.3 Verify Time Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_time$"))
async def vsub_time_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    AWAITING_INPUT.pop(query.from_user.id, None)
    cfg = await db.get_verify_step_config(step)
    info = STEP_NAMES.get(step, STEP_NAMES[1])
    ord_name = info["ord"]

    current_sec = cfg.get("time", 86400 if step == 1 else (TWO_VERIFY_GAP if step == 2 else THREE_VERIFY_GAP))
    time_display = format_verify_time_display(current_sec)

    text = (
        f"⏳ <b>{ord_name} VERIFY TIME:</b>\n\n"
        "❝ <b>VERIFICATION TIME:</b> DURATION FOR WHICH USER GETS BOT ACCESS AFTER COMPLETING ACCESS TOKEN. ❞\n\n"
        f"<b>TIME</b> - {time_display}"
    )

    buttons = [
        [InlineKeyboardButton("SET VERIFY TIME", callback_data=f"vflow_{step}_time")],
        [InlineKeyboardButton("RESET TIME", callback_data=f"vdel_{step}_time")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
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
    default_time = 86400 if step == 1 else (TWO_VERIFY_GAP if step == 2 else THREE_VERIFY_GAP)
    await db.update_verify_step_config(step, {"time": default_time})
    await query.answer("SUCCESSFULLY RESET VERIFY TIME ✅", show_alert=True)
    await vsub_time_cb(client, query)


# --- 3.4 Anti-Bypass Time Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_antibypass$"))
async def vsub_antibypass_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    AWAITING_INPUT.pop(query.from_user.id, None)
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
        [InlineKeyboardButton("SET BYPASS TIME", callback_data=f"vflow_{step}_antibypass")],
        [InlineKeyboardButton("RESET BYPASS TIME (12s)", callback_data=f"vdel_{step}_antibypass")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
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
    await query.answer("SUCCESSFULLY RESET BYPASS TIME ✅", show_alert=True)
    await vsub_antibypass_cb(client, query)


# --- 3.5 Verify Text Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_text$"))
async def vsub_text_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    AWAITING_INPUT.pop(query.from_user.id, None)
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
        [InlineKeyboardButton("SET VERIFY TEXT", callback_data=f"vflow_{step}_text")],
        [InlineKeyboardButton("SEE VERIFY TEXT", callback_data=f"vsee_{step}_text")],
        [InlineKeyboardButton("RESET VERIFY TEXT", callback_data=f"vdel_{step}_text")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
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


# --- 3.6 Verify Pic Sub-Screen ---
@Client.on_callback_query(filters.regex(r"^vsub_(\d+)_pic$"))
async def vsub_pic_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    AWAITING_INPUT.pop(query.from_user.id, None)
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
        f"<b>PHOTO STATUS :</b> {photo_status}"
    )

    buttons = [
        [InlineKeyboardButton("SET VERIFY PIC", callback_data=f"vflow_{step}_pic")],
        [InlineKeyboardButton("DELETE VERIFY PIC", callback_data=f"vdel_{step}_pic")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]
    ]

    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
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
# 4. Interactive Input Initiation (vflow_*)
# =========================================================================

@Client.on_callback_query(filters.regex(r"^vflow_(\d+)_(shortener_url|tutorial|time|antibypass|text|pic)$"))
async def vflow_initiate_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    step = int(query.matches[0].group(1))
    flow_type = query.matches[0].group(2)
    chat_id = query.message.chat.id

    if flow_type == "shortener_url":
        text = (
            "<b>SEND ME A SHORTLINK URL...</b>\n\n"
            "<b>FORMAT :</b>\n\n"
            "<code>https://vjlink.online</code> - ❌\n\n"
            "<code>vjlink.online</code> - ✅\n\n"
            "<code>/cancel</code> - CANCEL THIS PROCESS."
        )

    elif flow_type == "tutorial":
        text = (
            "<b>SEND ME A TUTORIAL LINK...</b>\n\n"
            "<code>/cancel</code> - CANCEL THIS PROCESS."
        )

    elif flow_type == "time":
        text = (
            "<b>SEND ME A VERIFICATION TIME...</b>\n\n"
            "<b>FORMAT :</b>\n\n"
            "1 Day - <code>1440m</code> or <code>1d</code>\n"
            "1 Hour - <code>60m</code> or <code>1h</code>\n"
            "10 Minutes - <code>10m</code>\n\n"
            "<code>/cancel</code> - CANCEL THIS PROCESS."
        )

    elif flow_type == "antibypass":
        text = (
            "<b>SEND ME ANTI-BYPASS TIME IN SECONDS...</b>\n\n"
            "Example : <code>12</code> or <code>15</code>\n\n"
            "<code>/cancel</code> - CANCEL THIS PROCESS."
        )

    elif flow_type == "text":
        text = (
            "<b>SEND ME CUSTOM VERIFICATION TEXT...</b>\n\n"
            "You can use <code>{mention}</code> for user tag.\n\n"
            "<code>/cancel</code> - CANCEL THIS PROCESS."
        )

    elif flow_type == "pic":
        text = (
            "<b>SEND ME A PHOTO OR IMAGE LINK...</b>\n\n"
            "<code>/cancel</code> - CANCEL THIS PROCESS."
        )

    # Delete previous menu message to prevent stacking
    try:
        await query.message.delete()
    except Exception:
        pass

    prompt_msg = await client.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )

    AWAITING_INPUT[query.from_user.id] = {
        "type": flow_type,
        "step": step,
        "prompt_msg_id": prompt_msg.id,
        "temp_data": {}
    }
    await query.answer()


# =========================================================================
# 5. Log Channel Menu
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

    AWAITING_INPUT.pop(query.from_user.id, None)
    text, markup = await get_log_channel_markup()
    try:
        await query.message.edit_text(
            text=text,
            reply_markup=markup,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        await query.message.reply_text(
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
    try:
        await query.message.edit_text(
            text=text,
            reply_markup=markup,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^vact_set_log_channel$"))
async def vact_set_log_channel_cb(client: Client, query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return await query.answer("⛔️ Access Denied!", show_alert=True)

    chat_id = query.message.chat.id
    try:
        await query.message.delete()
    except Exception:
        pass

    text = (
        "<b>SEND ME VERIFY LOG CHANNEL ID...</b>\n\n"
        "Example : <code>-1001234567890</code> or Forward a message from channel.\n\n"
        "<code>/cancel</code> - CANCEL THIS PROCESS."
    )
    prompt_msg = await client.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=enums.ParseMode.HTML
    )

    AWAITING_INPUT[query.from_user.id] = {
        "type": "log_channel",
        "step": 0,
        "prompt_msg_id": prompt_msg.id,
        "temp_data": {}
    }
    await query.answer()


# =========================================================================
# 6. /cancel Command Handler (group=-1)
# =========================================================================

@Client.on_message(filters.command("cancel") & filters.private, group=-1)
async def cancel_input_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    if user_id in AWAITING_INPUT:
        state = AWAITING_INPUT.pop(user_id)
        step = state.get("step", 1)
        prompt_id = state.get("prompt_msg_id")

        try:
            await message.delete()
        except Exception:
            pass
        if prompt_id:
            await safe_delete(client, message.chat.id, prompt_id)

        btn = [[InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}" if step else "verify_manage_panel")]]
        await client.send_message(
            chat_id=message.chat.id,
            text="<b>PROCESS CANCELLED ❌</b>",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        message.stop_propagation()
    else:
        message.continue_propagation()


# =========================================================================
# 7. Incoming Message Processor (group=-1 with stop_propagation)
# =========================================================================

@Client.on_message(filters.private & ~filters.command(["start", "admin", "adminpanel", "settings", "cancel"]), group=-1)
async def verify_settings_interactive_listener(client: Client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id) or user_id not in AWAITING_INPUT:
        message.continue_propagation()
        return

    # Critical: Stop propagation so pmfilter / search bot will NOT process this message!
    message.stop_propagation()

    state = AWAITING_INPUT[user_id]
    flow_type = state["type"]
    step = state.get("step", 1)
    prompt_id = state.get("prompt_msg_id")
    chat_id = message.chat.id

    # 1. Shortener URL (Step 1 of 2)
    if flow_type == "shortener_url":
        raw_url = (message.text or "").strip()
        cleaned_url = clean_domain(raw_url)
        
        # Clean user message and previous prompt
        try:
            await message.delete()
        except Exception:
            pass
        if prompt_id:
            await safe_delete(client, chat_id, prompt_id)

        if not cleaned_url or "." not in cleaned_url:
            err_msg = await client.send_message(
                chat_id=chat_id,
                text=(
                    "❌ <b>Invalid Domain Name!</b>\n\n"
                    "<b>FORMAT :</b>\n\n"
                    "<code>https://vjlink.online</code> - ❌\n\n"
                    "<code>vjlink.online</code> - ✅\n\n"
                    "<code>/cancel</code> - CANCEL THIS PROCESS."
                ),
                parse_mode=enums.ParseMode.HTML
            )
            state["prompt_msg_id"] = err_msg.id
            return

        # Save url into temp_data and transition to shortener_api step
        state["temp_data"]["site"] = cleaned_url
        state["type"] = "shortener_api"

        api_prompt = await client.send_message(
            chat_id=chat_id,
            text=(
                "<b>SEND ME SHORTLINK API...</b>\n\n"
                "<code>/cancel</code> - CANCEL THIS PROCESS."
            ),
            parse_mode=enums.ParseMode.HTML
        )
        state["prompt_msg_id"] = api_prompt.id
        return

    # 2. Shortener API (Step 2 of 2)
    if flow_type == "shortener_api":
        api_key = (message.text or "").strip()
        site_url = state["temp_data"].get("site", "")
        AWAITING_INPUT.pop(user_id, None)

        try:
            await message.delete()
        except Exception:
            pass
        if prompt_id:
            await safe_delete(client, chat_id, prompt_id)

        if not api_key:
            err_msg = await client.send_message(chat_id=chat_id, text="❌ API Key cannot be empty.")
            return

        await db.update_verify_step_config(step, {
            "shortener_site": site_url,
            "shortener_api": api_key
        })

        btn = [[InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]]
        await client.send_message(
            chat_id=chat_id,
            text="<b>SUCCESSFULLY SET SHORTLINK ✅</b>",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        return

    # 3. Tutorial Link
    if flow_type == "tutorial":
        tutorial_link = (message.text or "").strip()
        AWAITING_INPUT.pop(user_id, None)

        try:
            await message.delete()
        except Exception:
            pass
        if prompt_id:
            await safe_delete(client, chat_id, prompt_id)

        if not tutorial_link:
            return await client.send_message(chat_id=chat_id, text="❌ Tutorial link cannot be empty.")

        await db.update_verify_step_config(step, {
            "tutorial": tutorial_link
        })

        btn = [[InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]]
        await client.send_message(
            chat_id=chat_id,
            text="<b>SUCCESSFULLY SET TUTORIAL LINK ✅</b>",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        return

    # 4. Verify Time
    if flow_type == "time":
        time_text = (message.text or "").strip()
        AWAITING_INPUT.pop(user_id, None)

        try:
            await message.delete()
        except Exception:
            pass
        if prompt_id:
            await safe_delete(client, chat_id, prompt_id)

        seconds = parse_time_to_seconds(time_text)
        if seconds <= 0:
            seconds = 86400

        await db.update_verify_step_config(step, {
            "time": seconds
        })

        btn = [[InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]]
        await client.send_message(
            chat_id=chat_id,
            text="<b>SUCCESSFULLY SET VERIFICATION TIME ✅</b>",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        return

    # 5. Anti-Bypass Time
    if flow_type == "antibypass":
        bypass_text = (message.text or "").strip()
        AWAITING_INPUT.pop(user_id, None)

        try:
            await message.delete()
        except Exception:
            pass
        if prompt_id:
            await safe_delete(client, chat_id, prompt_id)

        try:
            bypass_sec = int(bypass_text)
        except Exception:
            bypass_sec = 12

        await db.update_verify_step_config(step, {
            "anti_bypass_time": bypass_sec
        })

        btn = [[InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]]
        await client.send_message(
            chat_id=chat_id,
            text="<b>SUCCESSFULLY SET ANTI-BYPASS TIME ✅</b>",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        return

    # 6. Verify Text
    if flow_type == "text":
        raw_text = message.text.html if hasattr(message.text, 'html') and message.text.html else (message.text or "")
        AWAITING_INPUT.pop(user_id, None)

        try:
            await message.delete()
        except Exception:
            pass
        if prompt_id:
            await safe_delete(client, chat_id, prompt_id)

        if not raw_text:
            return await client.send_message(chat_id=chat_id, text="❌ Text message cannot be empty.")

        await db.update_verify_step_config(step, {
            "text": raw_text
        })

        btn = [[InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]]
        await client.send_message(
            chat_id=chat_id,
            text="<b>SUCCESSFULLY SET VERIFY TEXT ✅</b>",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        return

    # 7. Verify Pic
    if flow_type == "pic":
        pic_url = ""
        if message.photo:
            pic_url = message.photo.file_id
        elif message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
            pic_url = message.text.strip()
        else:
            return await client.send_message(chat_id=chat_id, text="❌ Please send a photo directly or provide an image link.")

        AWAITING_INPUT.pop(user_id, None)
        try:
            await message.delete()
        except Exception:
            pass
        if prompt_id:
            await safe_delete(client, chat_id, prompt_id)

        await db.update_verify_step_config(step, {
            "pic": pic_url
        })

        btn = [[InlineKeyboardButton("‹ BACK", callback_data=f"vmenu_{step}")]]
        await client.send_message(
            chat_id=chat_id,
            text="<b>SUCCESSFULLY SET VERIFY PIC ✅</b>",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        return

    # 8. Log Channel
    if flow_type == "log_channel":
        AWAITING_INPUT.pop(user_id, None)
        try:
            await message.delete()
        except Exception:
            pass
        if prompt_id:
            await safe_delete(client, chat_id, prompt_id)

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
            return await client.send_message(
                chat_id=chat_id,
                text="❌ <b>Invalid Channel ID!</b> Please send numeric ID like <code>-1001234567890</code>."
            )

        try:
            chat = await client.get_chat(target_channel_id)
            me = await client.get_me()
            member = await chat.get_member(me.id)
            if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return await client.send_message(
                    chat_id=chat_id,
                    text="❌ The bot is not an admin in that channel! Please promote the bot to Admin and try again."
                )
        except Exception as e:
            return await client.send_message(
                chat_id=chat_id,
                text=f"❌ Error accessing channel: <code>{e}</code>\nMake sure bot is admin with post permissions!"
            )

        await db.set_verify_log_channel(target_channel_id)
        btn = [[InlineKeyboardButton("‹ BACK", callback_data="vmenu_log_channel")]]
        await client.send_message(
            chat_id=chat_id,
            text="<b>SUCCESSFULLY SET VERIFY LOG CHANNEL ✅</b>",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        return
