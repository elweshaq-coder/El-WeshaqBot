𝐑𝐎𝐁𝐄𝐑𝐓 𝐀𝐒𝐈𝐑 𖠕:
try:
            await bot.send_message(user_id,
                "✅ تم قبول طلب إنشاء حساب ICHANCY وحفظه:\n"
                f"👤 <code>{escape(ich['username'])}</code>\n"
                f"🔒 <code>{escape(ich['password'])}</code>"
            )
        except Exception:
            pass

    elif t in ("ichancy_topup", "ichancy_withdraw"):
        # عمليات خارجية، فقط إعلام المستخدم
        set_request_status(req_id, "approved")
        action = "شحن حسابك" if t == "ichancy_topup" else "سحب من حسابك"
        try:
            await bot.send_message(user_id, f"✅ تم قبول طلب {action}. سيتم التنفيذ قريبًا.")
        except Exception:
            pass

    else:
        set_request_status(req_id, "approved")

    await c.answer("تمت الموافقة ✔️")

@dp.callback_query(F.data.startswith("req_no:"))
async def req_no(c: CallbackQuery):
    if not admin_only(c.from_user.id):
        return await c.answer("ممنوع.", show_alert=True)
    req_id = c.data.split(":")[1]
    r = get_request(req_id)
    if not r or r["status"] != "pending":
        return await c.answer("طلب غير صالح أو تم التعامل معه.", show_alert=True)
    set_request_status(req_id, "rejected")
    user_id = r["user_id"]
    try:
        await bot.send_message(user_id, "❌ تم رفض طلبك من قبل الأدمن.")
    except Exception:
        pass
    await c.answer("تم الرفض ✖️")

# ------------------ أوامر مساعدة ------------------

@dp.message(Command("balance"))
async def cmd_balance(m: Message):
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    await m.answer(f"رصيدك الحالي: <b>{fmt_syp(u['balance'])}</b>")

@dp.message(Command("id"))
async def cmd_id(m: Message):
    await m.answer(f"ID الخاص بك: <code>{m.from_user.id}</code>")

# ------------------ تشغيل البوت ------------------

async def main():
    print("Bot is running...")
    await dp.start_polling(bot)

if name == "main":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")# -*- coding: utf-8 -*-
"""
Bot: ICHANCY Admin/Manual Topups & Withdrawals
Platform: Python + aiogram v3 (works on Pydroid3/Termux)
Author: ChatGPT
Notes:
 - Inline keyboards Arabic UI
 - JSON persistence
 - Single-file, no splitting
"""

import asyncio
import json
import os
import time
import re
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

# ================== إعداداتك ==================
BOT_TOKEN = "8200934380:AAFf1V53wQPfUk_emAZtlFGQMMmJiL86c6E"
ADMIN_ID = 7691741033
CHANNEL_URL = "https://t.me/Taehar_ichancy"
SUPPORT_HANDLE = "@ASE_ER11"

# القيم الافتراضية (قابلة للتعديل من لوحة الأدمن)
DEFAULT_SYR_CODE = "93492451"  # كود تحويل سيريتل
DEFAULT_SHAM_ACCOUNT = "6555c7d5d062c9912470c47237d1d1fa"  # حساب شام كاش

DATA_FILE = "ichancy_bot_data.json"

# ================== حفظ/تحميل البيانات ==================

def now_ts() -> int:
    return int(time.time())

def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        data = {
            "users": {},  # user_id -> info
            "settings": {
                "syr_code": DEFAULT_SYR_CODE,
                "sham_account": DEFAULT_SHAM_ACCOUNT,
                "channel": CHANNEL_URL,
                "support": SUPPORT_HANDLE,
                "admin_id": ADMIN_ID
            },
            "requests": {},  # req_id -> details
            "gift_codes": {} # code -> {amount, creator, used_by}
        }
        save_data(data)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data: Dict[str, Any]) -> None:
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)

DATA = load_data()

# ================== هياكل المستخدم ==================

def ensure_user(user_id: int, name: str) -> Dict[str, Any]:
    u = DATA["users"].get(str(user_id))
    if not u:
        u = {
            "id": user_id,
            "name": name,
            "balance": 0,
            "banned": False,
            "ichancy": None,  # {"username":..., "password":...}
            "created_at": now_ts()
        }
        DATA["users"][str(user_id)] = u
        save_data(DATA)
    return u

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    return DATA["users"].get(str(user_id))

def update_user(user_id: int, fields: Dict[str, Any]):
    u = get_user(user_id)
    if not u:
        return
    u.update(fields)
    save_data(DATA)

def fmt_syp(amount: int) -> str:
    return f"{amount:,} ل.س".replace(",", ".")

# ================== الطلبات (شحن/سحب/إنشاء حساب) ==================

def new_request(req_type: str, user_id: int, payload: Dict[str, Any]) -> str:
    # req_type: topup_bot / withdraw_bot / ichancy_topup / ichancy_withdraw / create_ichancy
    req_id = f"R{int(time.time()*1000)}"
    DATA["requests"][req_id] = {
        "id": req_id,
        "type": req_type,
        "user_id": user_id,
        "payload": payload,
        "status": "pending",
        "created_at": now_ts()
    }
    save_data(DATA)
    return req_id

def get_request(req_id: str) -> Optional[Dict[str, Any]]:
    return DATA["requests"].get(req_id)

def set_request_status(req_id: str, status: str):
    r = get_request(req_id)
    if r:
        r["status"] = status
        r["updated_at"] = now_ts()
        save_data(DATA)

# ================== أزرار الواجهات ==================

def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="💳 حساب ICHANCY و شحنه", callback_data="menu_ichancy")],
        [InlineKeyboardButton(text="➕ شحن رصيد إلى البوت", callback_data="menu_topup_bot")],
        [InlineKeyboardButton(text="💸 سحب رصيد من البوت", callback_data="menu_withdraw_bot")],
        [InlineKeyboardButton(text="🎁 استخدم كود هدية", callback_data="use_gift")],
        [InlineKeyboardButton(text="🆘 الدعم", url=f"https://t.me/{SUPPORT_HANDLE.lstrip('@')}")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠️ لوحة الأدمن", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ichancy_menu_kb(has_account: bool) -> InlineKeyboardMarkup:
    rows = []
    rows.append([InlineKeyboardButton(text="🆕 إنشاء حساب ICHANCY", callback_data="ichancy_create")])
    rows.append([InlineKeyboardButton(text="➕ شحن رصيد إلى حسابي", callback_data="ichancy_topup")])
    rows.append([InlineKeyboardButton(text="💸 سحب رصيد من حسابي", callback_data="ichancy_withdraw")])
    if has_account:
        rows.append([InlineKeyboardButton(text="👤 عرض حسابي المحفوظ", callback_data="ichancy_show")])
    rows.append([InlineKeyboardButton(text="⬅️ رجوع", callback_data="back_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def topup_bot_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="سيريتل كاش", callback_data="topup_bot_syr")],
        [InlineKeyboardButton(text="شام كاش", callback_data="topup_bot_sham")],
        [InlineKeyboardButton(text="⬅️ رجوع", callback_data="back_home")],
    ])

def withdraw_bot_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="سيريتل كاش", callback_data="withdraw_bot_syr")],
        [InlineKeyboardButton(text="شام كاش", callback_data="withdraw_bot_sham")],
        [InlineKeyboardButton(text="⬅️ رجوع", callback_data="back_home")],
    ])

def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 عرض مستخدم بالـ ID", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="🎁 إنشاء كود هدية", callback_data="admin_new_gift")],
        [InlineKeyboardButton(text="✏️ تغيير كود سيريتل", callback_data="admin_set_syr")],
        [InlineKeyboardButton(text="✏️ تغيير حساب شام كاش", callback_data="admin_set_sham")],
        [InlineKeyboardButton(text="📂 الطلبات المعلقة", callback_data="admin_list_pending")],
        [InlineKeyboardButton(text="⬅️ رجوع", callback_data="back_home")],
    ])

def req_admin_kb(req_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ موافقة", callback_data=f"req_ok:{req_id}"),
            InlineKeyboardButton(text="❌ رفض", callback_data=f"req_no:{req_id}")
        ]
    ])

def user_manage_kb(user_id: int, banned: bool) -> InlineKeyboardMarkup:
    btns = []
    if banned:
        btns.append(InlineKeyboardButton(text="🔓 رفع الحظر", callback_data=f"admin_unban:{user_id}"))
    else:
        btns.append(InlineKeyboardButton(text="⛔ حظر المستخدم", callback_data=f"admin_ban:{user_id}"))
    btns2 = [
        InlineKeyboardButton(text="➕ شحن رصيد", callback_data=f"admin_addbal:{user_id}"),
        InlineKeyboardButton(text="➖ خصم رصيد", callback_data=f"admin_subbal:{user_id}")
    ]
    btns3 = [InlineKeyboardButton(text="📨 إرسال حساب ICHANCY", callback_data=f"admin_send_acc:{user_id}")]
    return InlineKeyboardMarkup(inline_keyboard=[
        btns, btns2, btns3,
        [InlineKeyboardButton(text="⬅️ رجوع", callback_data="admin_panel")]
    ])

# ================== FSM الحالات ==================

class CreateICH(StatesGroup):
    ask_user = State()
    ask_pass = State()

class ICHTopup(StatesGroup):
    ask_amount = State()
    ask_note = State()

class ICHWithdraw(StatesGroup):
    ask_amount = State()
    ask_note = State()

class TopupBotSYR(StatesGroup):
    ask_tx = State()
    ask_amount = State()

class TopupBotSHAM(StatesGroup):
    ask_tx = State()
    ask_amount = State()

class WithdrawBotSYR(StatesGroup):
    ask_amount = State()
    ask_account = State()

class WithdrawBotSHAM(StatesGroup):
    ask_amount = State()
    ask_account = State()

class GiftUse(StatesGroup):
    ask_code = State()

class AdminFindUser(StatesGroup):
    ask_id = State()

class AdminBal(StatesGroup):
    add_amount = State()
    sub_amount = State()

class AdminSetSYR(StatesGroup):
    ask_code = State()

class AdminSetSHAM(StatesGroup):
    ask_acc = State()

class AdminNewGift(StatesGroup):
    ask_amount = State()

class AdminSendAcc(StatesGroup):
    ask_username = State()
    ask_password = State()

# ================== البوت ==================

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# ------------------ أدوات عامة ------------------

async def send_admin(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception:
        pass

def escape(s: str) -> str:
    return s.replace("<", "‹").replace(">", "›")

# ------------------ /start ------------------

@dp.message(CommandStart())
async def start_cmd(m: Message, state: FSMContext):
    u = ensure_user(m.from_user.id, m.from_user.full_name or m.from_user.username or str(m.from_user.id))
    if u["banned"]:
        await m.answer("⚠️ لقد تم حظرك من استخدام هذا البوت.")
        return
    bal = fmt_syp(int(u["balance"]))
    ch = DATA["settings"]["channel"]
    text = (
        f"أهلًا {escape(u['name'])} 👋\n"
        f"رصيدك الحالي في البوت: <b>{bal}</b>\n\n"
        f"تابعنا على قناتنا: <a href=\"{ch}\">{ch}</a>\n"
    )
    is_admin = (m.from_user.id == ADMIN_ID)
    await m.answer(text, reply_markup=main_menu_kb(is_admin))

@dp.callback_query(F.data == "back_home")
async def back_home(c: CallbackQuery):
    u = ensure_user(c.from_user.id, c.from_user.full_name or "")
    is_admin = (c.from_user.id == ADMIN_ID)
    await c.message.edit_text("القائمة الرئيسية:", reply_markup=main_menu_kb(is_admin))
    await c.answer()

# ------------------ قائمة ICHANCY ------------------

@dp.callback_query(F.data == "menu_ichancy")
async def menu_ichancy(c: CallbackQuery):
    u = ensure_user(c.from_user.id, c.from_user.full_name or "")
    has_acc = bool(u["ichancy"])
    txt = "اختر ما تريد بخصوص حساب ICHANCY:"
    await c.message.edit_text(txt, reply_markup=ichancy_menu_kb(has_acc))
    await c.answer()

@dp.callback_query(F.data == "ichancy_show")
async def ich_show(c: CallbackQuery):
    u = get_user(c.from_user.id)
    if not u or not u.get("ichancy"):
        await c.answer("لا يوجد حساب محفوظ.", show_alert=True)
        return
    acc = u["ichancy"]
    txt = (
        "بيانات حسابك المحفوظ:\n"
        f"👤 المستخدم: <code>{escape(acc['username'])}</code>\n"
        f"🔒 كلمة السر: <code>{escape(acc['password'])}</code>\n"
    )
    await c.message.edit_text(txt, reply_markup=ichancy_menu_kb(True))
    await c.answer()

# إنشاء حساب
@dp.callback_query(F.data == "ichancy_create")
async def ich_create_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(CreateICH.ask_user)
    await c.message.edit_text("أرسل اسم المستخدم الذي تريده لحساب ICHANCY:")
    await c.answer()

@dp.message(CreateICH.ask_user)
async def ich_create_user(m: Message, state: FSMContext):
    username = m.text.strip()
    if len(username) < 3:
        await m.answer("الاسم قصير جدًا. أرسل اسمًا أطول (3 أحرف على الأقل).")
        return
    await state.update_data(ich_user=username)
    await state.set_state(CreateICH.ask_pass)
    await m.answer("أرسل كلمة السر المطلوبة:")

@dp.message(CreateICH.ask_pass)
async def ich_create_pass(m: Message, state: FSMContext):
    password = m.text.strip()
    data = await state.get_data()
    username = data["ich_user"]
    req_id = new_request("create_ichancy", m.from_user.id, {
        "username": username, "password": password
    })
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    await m.answer("✅ تم إرسال طلب إنشاء الحساب إلى الأدمن، بانتظار الموافقة.")
    txt_admin = (
        f"🆕 طلب إنشاء حساب ICHANCY\n"
        f"Req: {req_id}\n"
        f"من: {u['name']} (ID: {u['id']})\n"
        f"المستخدم المراد: {username}\n"
        f"كلمة السر: {password}\n"
    )
    await send_admin(txt_admin, reply_markup=req_admin_kb(req_id))
    await state.clear()

# شحن حساب ICHANCY (طلب للأدمن)
@dp.callback_query(F.data == "ichancy_topup")
async def ich_topup_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(ICHTopup.ask_amount)
    await c.message.edit_text("أرسل مبلغ الشحن المطلوب إلى حسابك في ICHANCY (بالليرة السورية):")
    await c.answer()

@dp.message(ICHTopup.ask_amount)
async def ich_topup_amount(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("الرجاء إرسال مبلغ صحيح (أرقام فقط).")
        return
    amount = int(m.text)
    await state.update_data(amount=amount)
    await state.set_state(ICHTopup.ask_note)
    await m.answer("أرسل ملاحظة/تفاصيل إضافية (أو اكتب - لا شيء -):")

@dp.message(ICHTopup.ask_note)
async def ich_topup_note(m: Message, state: FSMContext):
    note = m.text.strip()
    data = await state.get_data()
    amount = data["amount"]
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    req_id = new_request("ichancy_topup", m.from_user.id, {
        "amount": amount, "note": note, "ichancy": u.get("ichancy")
    })
    await m.answer("✅ تم إرسال طلب شحن حساب ICHANCY إلى الأدمن.")
    txt = (
        f"➕ طلب شحن حساب ICHANCY\n"
        f"Req: {req_id}\n"
        f"من: {u['name']} (ID: {u['id']})\n"
        f"المبلغ: {fmt_syp(amount)}\n"
        f"الحساب: {u.get('ichancy')}\n"
        f"ملاحظة: {note}"
    )
    await send_admin(txt, reply_markup=req_admin_kb(req_id))
    await state.clear()

# سحب من حساب ICHANCY (طلب للأدمن)
@dp.callback_query(F.data == "ichancy_withdraw")
async def ich_withdraw_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(ICHWithdraw.ask_amount)
    await c.message.edit_text("أرسل مبلغ السحب المطلوب من حساب ICHANCY (بالليرة السورية):")
    await c.answer()

@dp.message(ICHWithdraw.ask_amount)
async def ich_withdraw_amount(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("الرجاء إرسال مبلغ صحيح.")
        return
    amount = int(m.text)
    await state.update_data(amount=amount)
    await state.set_state(ICHWithdraw.ask_note)
    await m.answer("أرسل ملاحظة/تفاصيل (مثلاً إلى أين تريد التحويل) أو اكتب - لا شيء -:")

@dp.message(ICHWithdraw.ask_note)
async def ich_withdraw_note(m: Message, state: FSMContext):
    note = m.text.strip()
    data = await state.get_data()
    amount = data["amount"]
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    req_id = new_request("ichancy_withdraw", m.from_user.id, {
        "amount": amount, "note": note, "ichancy": u.get("ichancy")
    })
    await m.answer("✅ تم إرسال طلب سحب من حساب ICHANCY إلى الأدمن.")
    txt = (
        f"💸 طلب سحب من حساب ICHANCY\n"
        f"Req: {req_id}\n"
        f"من: {u['name']} (ID: {u['id']})\n"
        f"المبلغ: {fmt_syp(amount)}\n"
        f"الحساب: {u.get('ichancy')}\n"
        f"ملاحظة: {note}"
    )
    await send_admin(txt, reply_markup=req_admin_kb(req_id))
    await state.clear()

# ------------------ شحن رصيد إلى البوت ------------------

@dp.callback_query(F.data == "menu_topup_bot")
async def menu_topup_bot(c: CallbackQuery):
    s = DATA["settings"]
    txt = (
        "اختر طريقة الشحن:\n\n"
        f"🔢 كود سيريتل الحالي: <code>{s['syr_code']}</code>\n"
        f"🏦 حساب شام كاش الحالي: <code>{s['sham_account']}</code>"
    )
    await c.message.edit_text(txt, reply_markup=topup_bot_menu_kb())
    await c.answer()

# سيريتل
@dp.callback_query(F.data == "topup_bot_syr")
async def topup_syr_start(c: CallbackQuery, state: FSMContext):
    code = DATA["settings"]["syr_code"]
    txt = (
        "قم بتحويل المبلغ المراد إيداعه إلى الكود التالي (تحويل يدوي):\n"
        f"<code>{code}</code>\n\n"
        "ثم أرسل <b>رقم عملية التحويل</b>:"
    )
    await state.set_state(TopupBotSYR.ask_tx)
    await c.message.edit_text(txt)
    await c.answer()

@dp.message(TopupBotSYR.ask_tx)
async def topup_syr_tx(m: Message, state: FSMContext):
    tx = m.text.strip()
    if len(tx) < 5:
        await m.answer("الرمز قصير. أعد إرسال رقم العملية الصحيح.")
        return
    await state.update_data(tx=tx)
    await state.set_state(TopupBotSYR.ask_amount)
    await m.answer("أرسل <b>المبلغ</b> الذي تريد شحنه (بالليرة السورية):")

@dp.message(TopupBotSYR.ask_amount)
async def topup_syr_amount(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("الرجاء إرسال مبلغ صحيح.")
        return
    amount = int(m.text)
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    data = await state.get_data()
    tx = data["tx"]
    req_id = new_request("topup_bot", m.from_user.id, {"method": "syr", "tx": tx, "amount": amount})
    await m.answer("✅ تم إرسال طلب الشحن إلى الأدمن للمراجعة.")
    txt = (
        f"➕ طلب شحن للبوت (سيريتل)\n"
        f"Req: {req_id}\n"
        f"من: {u['name']} (ID: {u['id']})\n"
        f"المبلغ: {fmt_syp(amount)}\n"
        f"رقم العملية: {tx}"
    )
    await send_admin(txt, reply_markup=req_admin_kb(req_id))
    await state.clear()

# شام
@dp.callback_query(F.data == "topup_bot_sham")
async def topup_sham_start(c: CallbackQuery, state: FSMContext):
    acc = DATA["settings"]["sham_account"]
    txt = (
        "قم بإرسال المبلغ المراد إيداعه إلى حساب شام كاش:\n"
        f"<code>{acc}</code>\n\n"
        "ثم أرسل <b>رقم العملية</b> (7 أو 8 أرقام):"
    )
    await state.set_state(TopupBotSHAM.ask_tx)
    await c.message.edit_text(txt)
    await c.answer()

@dp.message(TopupBotSHAM.ask_tx)
async def topup_sham_tx(m: Message, state: FSMContext):
    tx = m.text.strip()
    if not re.fullmatch(r"\d{7,8}", tx):
        await m.answer("الرجاء إرسال رقم عملية صحيح (7 أو 8 أرقام).")
        return
    await state.update_data(tx=tx)
    await state.set_state(TopupBotSHAM.ask_amount)
    await m.answer("أرسل <b>المبلغ</b> الذي تريد شحنه (بالليرة السورية):")

@dp.message(TopupBotSHAM.ask_amount)
async def topup_sham_amount(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("الرجاء إرسال مبلغ صحيح.")
        return
    amount = int(m.text)
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    data = await state.get_data()
    tx = data["tx"]
    req_id = new_request("topup_bot", m.from_user.id, {"method": "sham", "tx": tx, "amount": amount})
    await m.answer("✅ تم إرسال طلب الشحن إلى الأدمن للمراجعة.")
    txt = (
        f"➕ طلب شحن للبوت (شام كاش)\n"
        f"Req: {req_id}\n"
        f"من: {u['name']} (ID: {u['id']})\n"
        f"المبلغ: {fmt_syp(amount)}\n"
        f"رقم العملية: {tx}"
    )
    await send_admin(txt, reply_markup=req_admin_kb(req_id))
    await state.clear()

# ------------------ سحب من البوت ------------------

@dp.callback_query(F.data == "menu_withdraw_bot")
async def menu_withdraw_bot(c: CallbackQuery):
    await c.message.edit_text("اختر طريقة السحب من رصيدك في البوت:", reply_markup=withdraw_bot_menu_kb())
    await c.answer()

# سيريتل
@dp.callback_query(F.data == "withdraw_bot_syr")
async def wb_syr_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(WithdrawBotSYR.ask_amount)
    await c.message.edit_text("أرسل المبلغ المراد سحبه (الحد الأدنى 25000 ل.س):")
    await c.answer()

@dp.message(WithdrawBotSYR.ask_amount)
async def wb_syr_amount(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("الرجاء إرسال مبلغ صحيح.")
        return
    amount = int(m.text)
    if amount < 25000:
        await m.answer("الحد الأدنى للسحب 25000 ل.س.")
        return
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    if u["balance"] < amount:
        await m.answer("رصيدك غير كافٍ.")
        return
    await state.update_data(amount=amount)
    await state.set_state(WithdrawBotSYR.ask_account)
    await m.answer("أرسل رقم حساب سيريتل كاش الخاص بك:")

@dp.message(WithdrawBotSYR.ask_account)
async def wb_syr_account(m: Message, state: FSMContext):
    account = m.text.strip()
    data = await state.get_data()
    amount = data["amount"]
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    req_id = new_request("withdraw_bot", m.from_user.id, {
        "method": "syr", "amount": amount, "account": account
    })
    await m.answer("✅ تم إرسال طلب السحب إلى الأدمن. سيتم المعالجة قريبًا.")
    txt = (
        f"💸 طلب سحب من البوت (سيريتل)\n"
        f"Req: {req_id}\n"
        f"من: {u['name']} (ID: {u['id']})\n"
        f"المبلغ: {fmt_syp(amount)}\n"
        f"حساب المستلم: {account}\n"
        f"رصيد المستخدم الحالي: {fmt_syp(u['balance'])}"
    )
    await send_admin(txt, reply_markup=req_admin_kb(req_id))
    await state.clear()

# شام
@dp.callback_query(F.data == "withdraw_bot_sham")
async def wb_sham_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(WithdrawBotSHAM.ask_amount)
    await c.message.edit_text("أرسل المبلغ المراد سحبه (الحد الأدنى 25000 ل.س):")
    await c.answer()

@dp.message(WithdrawBotSHAM.ask_amount)
async def wb_sham_amount(m: Message, state: FSMContext):
    if not m.text.isdigit():
        await m.answer("الرجاء إرسال مبلغ صحيح.")
        return
    amount = int(m.text)
    if amount < 25000:
        await m.answer("الحد الأدنى للسحب 25000 ل.س.")
        return
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    if u["balance"] < amount:
        await m.answer("رصيدك غير كافٍ.")
        return
    await state.update_data(amount=amount)
    await state.set_state(WithdrawBotSHAM.ask_account)
    await m.answer("أرسل حساب/معرّف شام كاش الخاص بك:")

@dp.message(WithdrawBotSHAM.ask_account)
async def wb_sham_account(m: Message, state: FSMContext):
    account = m.text.strip()
    data = await state.get_data()
    amount = data["amount"]
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    req_id = new_request("withdraw_bot", m.from_user.id, {
        "method": "sham", "amount": amount, "account": account
    })
    await m.answer("✅ تم إرسال طلب السحب إلى الأدمن. سيتم المعالجة قريبًا.")
    txt = (
        f"💸 طلب سحب من البوت (شام كاش)\n"
        f"Req: {req_id}\n"
        f"من: {u['name']} (ID: {u['id']})\n"
        f"المبلغ: {fmt_syp(amount)}\n"
        f"حساب المستلم: {account}\n"
        f"رصيد المستخدم الحالي: {fmt_syp(u['balance'])}"
    )
    await send_admin(txt, reply_markup=req_admin_kb(req_id))
    await state.clear()

# ------------------ الهدايا ------------------

@dp.callback_query(F.data == "use_gift")
async def gift_use_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(GiftUse.ask_code)
    await c.message.edit_text("أرسل كود الهدية لاستخدامه (مرّة واحدة):")
    await c.answer()

@dp.message(GiftUse.ask_code)
async def gift_use_code(m: Message, state: FSMContext):
    code = m.text.strip().upper()
    g = DATA["gift_codes"].get(code)
    if not g:
        await m.answer("❌ كود غير صالح.")
        return
    if g.get("used_by"):
        await m.answer("❌ هذا الكود مستخدم سابقًا.")
        return
    amount = int(g["amount"])
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    u["balance"] += amount
    g["used_by"] = m.from_user.id
    save_data(DATA)
    await m.answer(f"✅ تم استخدام الكود وإضافة {fmt_syp(amount)} إلى رصيدك.")
    await state.clear()

# ------------------ لوحة الأدمن ------------------

def admin_only(user_id: int) -> bool:
    return user_id == ADMIN_ID

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(c: CallbackQuery):
    if not admin_only(c.from_user.id):
        await c.answer("لوحة خاصة بالأدمن.", show_alert=True)
        return
    await c.message.edit_text("🛠️ لوحة الأدمن:", reply_markup=admin_panel_kb())
    await c.answer()

@dp.callback_query(F.data == "admin_find_user")
async def admin_find_user(c: CallbackQuery, state: FSMContext):
    if not admin_only(c.from_user.id):
        await c.answer("ممنوع.", show_alert=True); return
    await state.set_state(AdminFindUser.ask_id)
    await c.message.edit_text("أرسل ID المستخدم الذي تريد عرض بياناته:")
    await c.answer()

@dp.message(AdminFindUser.ask_id)
async def admin_find_user_id(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id):
        await m.answer("ممنوع."); return
    if not m.text.isdigit():
        await m.answer("أرسل ID رقمي.")
        return
    uid = int(m.text)
    u = get_user(uid)
    if not u:
        await m.answer("لا يوجد مستخدم بهذا الـ ID.")
        await state.clear()
        return
    acc = u.get("ichancy")
    txt = (
        f"👤 {escape(u['name'])}\n"
        f"ID: {u['id']}\n"
        f"الرصيد: {fmt_syp(u['balance'])}\n"
        f"الحظر: {'نعم' if u['banned'] else 'لا'}\n"
        f"حساب ICHANCY: {acc}\n"
    )
    await m.answer(txt, reply_markup=user_manage_kb(uid, u['banned']))
    await state.clear()

@dp.callback_query(F.data.startswith("admin_ban:"))
async def admin_ban(c: CallbackQuery):
    if not admin_only(c.from_user.id):
        await c.answer("ممنوع.", show_alert=True); return
    uid = int(c.data.split(":")[1])
    u = get_user(uid)
    if not u:
        await c.answer("مستخدم غير موجود.", show_alert=True); return
    u["banned"] = True
    save_data(DATA)
    await c.message.edit_reply_markup(reply_markup=user_manage_kb(uid, True))
    await c.answer("تم الحظر.")

@dp.callback_query(F.data.startswith("admin_unban:"))
async def admin_unban(c: CallbackQuery):

if not admin_only(c.from_user.id):
        await c.answer("ممنوع.", show_alert=True); return
    uid = int(c.data.split(":")[1])
    u = get_user(uid)
    if not u:
        await c.answer("مستخدم غير موجود.", show_alert=True); return
    u["banned"] = False
    save_data(DATA)
    await c.message.edit_reply_markup(reply_markup=user_manage_kb(uid, False))
    await c.answer("تم رفع الحظر.")

# شحن/خصم رصيد من الأدمن
@dp.callback_query(F.data.startswith("admin_addbal:"))
async def admin_addbal(c: CallbackQuery, state: FSMContext):
    if not admin_only(c.from_user.id): return await c.answer("ممنوع.", show_alert=True)
    uid = int(c.data.split(":")[1])
    await state.set_state(AdminBal.add_amount)
    await state.update_data(target_uid=uid)
    await c.message.answer("أرسل مبلغ الشحن (أرقام فقط):")
    await c.answer()

@dp.message(AdminBal.add_amount)
async def admin_addbal_amount(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id): return await m.answer("ممنوع.")
    if not m.text.isdigit():
        await m.answer("أرسل مبلغ صحيح."); return
    amount = int(m.text)
    data = await state.get_data()
    uid = data["target_uid"]
    u = get_user(uid)
    if not u:
        await m.answer("المستخدم غير موجود."); return
    u["balance"] += amount
    save_data(DATA)
    await m.answer(f"تم شحن {fmt_syp(amount)} للمستخدم {u['name']}.")
    await state.clear()

@dp.callback_query(F.data.startswith("admin_subbal:"))
async def admin_subbal(c: CallbackQuery, state: FSMContext):
    if not admin_only(c.from_user.id): return await c.answer("ممنوع.", show_alert=True)
    uid = int(c.data.split(":")[1])
    await state.set_state(AdminBal.sub_amount)
    await state.update_data(target_uid=uid)
    await c.message.answer("أرسل مبلغ الخصم (أرقام فقط):")
    await c.answer()

@dp.message(AdminBal.sub_amount)
async def admin_subbal_amount(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id): return await m.answer("ممنوع.")
    if not m.text.isdigit():
        await m.answer("أرسل مبلغ صحيح."); return
    amount = int(m.text)
    data = await state.get_data()
    uid = data["target_uid"]
    u = get_user(uid)
    if not u:
        await m.answer("المستخدم غير موجود."); return
    if u["balance"] < amount:
        await m.answer("رصيد المستخدم غير كافٍ."); return
    u["balance"] -= amount
    save_data(DATA)
    await m.answer(f"تم خصم {fmt_syp(amount)} من المستخدم {u['name']}.")
    await state.clear()

# إرسال حساب ICHANCY للمستخدم يدويًا من الأدمن
@dp.callback_query(F.data.startswith("admin_send_acc:"))
async def admin_send_acc(c: CallbackQuery, state: FSMContext):
    if not admin_only(c.from_user.id): return await c.answer("ممنوع.", show_alert=True)
    uid = int(c.data.split(":")[1])
    await state.set_state(AdminSendAcc.ask_username)
    await state.update_data(target_uid=uid)
    await c.message.answer("أرسل اسم مستخدم ICHANCY الذي تريد إرساله:")
    await c.answer()

@dp.message(AdminSendAcc.ask_username)
async def admin_send_acc_user(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id): return await m.answer("ممنوع.")
    await state.update_data(ich_user=m.text.strip())
    await state.set_state(AdminSendAcc.ask_password)
    await m.answer("أرسل كلمة سر ICHANCY:")

@dp.message(AdminSendAcc.ask_password)
async def admin_send_acc_pass(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id): return await m.answer("ممنوع.")
    data = await state.get_data()
    uid = data["target_uid"]
    ich_user = data["ich_user"]
    ich_pass = m.text.strip()
    u = get_user(uid)
    if not u:
        await m.answer("المستخدم غير موجود."); return
    u["ichancy"] = {"username": ich_user, "password": ich_pass}
    save_data(DATA)
    try:
        await bot.send_message(chat_id=uid, text=(

"✅ تم إرسال بيانات حساب ICHANCY إليك:\n"
            f"👤 المستخدم: <code>{escape(ich_user)}</code>\n"
            f"🔒 كلمة السر: <code>{escape(ich_pass)}</code>"
        ))
    except Exception:
        pass
    await m.answer("تم حفظ وإرسال الحساب للمستخدم.")
    await state.clear()

# تغيير كود سيريتل من الأدمن
@dp.callback_query(F.data == "admin_set_syr")
async def admin_set_syr(c: CallbackQuery, state: FSMContext):
    if not admin_only(c.from_user.id):
        return await c.answer("ممنوع.", show_alert=True)
    await state.set_state(AdminSetSYR.ask_code)
    await c.message.edit_text("أرسل كود سيريتل الجديد:")
    await c.answer()

@dp.message(AdminSetSYR.ask_code)
async def admin_set_syr_code(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id): return await m.answer("ممنوع.")
    code = m.text.strip()
    DATA["settings"]["syr_code"] = code
    save_data(DATA)
    await m.answer(f"تم تحديث كود سيريتل إلى: <code>{code}</code>")
    await state.clear()

# تغيير حساب شام كاش من الأدمن
@dp.callback_query(F.data == "admin_set_sham")
async def admin_set_sham(c: CallbackQuery, state: FSMContext):
    if not admin_only(c.from_user.id):
        return await c.answer("ممنوع.", show_alert=True)
    await state.set_state(AdminSetSHAM.ask_acc)
    await c.message.edit_text("أرسل حساب شام كاش الجديد:")
    await c.answer()

@dp.message(AdminSetSHAM.ask_acc)
async def admin_set_sham_acc(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id): return await m.answer("ممنوع.")
    acc = m.text.strip()
    DATA["settings"]["sham_account"] = acc
    save_data(DATA)
    await m.answer(f"تم تحديث حساب شام كاش إلى: <code>{acc}</code>")
    await state.clear()

# إنشاء كود هدية
@dp.callback_query(F.data == "admin_new_gift")
async def admin_new_gift(c: CallbackQuery, state: FSMContext):
    if not admin_only(c.from_user.id):
        return await c.answer("ممنوع.", show_alert=True)
    await state.set_state(AdminNewGift.ask_amount)
    await c.message.edit_text("أرسل مبلغ الهدية (أرقام فقط):")
    await c.answer()

@dp.message(AdminNewGift.ask_amount)
async def admin_new_gift_amount(m: Message, state: FSMContext):
    if not admin_only(m.from_user.id): return await m.answer("ممنوع.")
    if not m.text.isdigit():
        await m.answer("أرسل مبلغ صحيح."); return
    amount = int(m.text)
    code = f"GIFT{int(time.time())}"
    DATA["gift_codes"][code] = {"amount": amount, "creator": ADMIN_ID, "used_by": None}
    save_data(DATA)
    await m.answer(f"✅ تم إنشاء كود: <code>{code}</code> بقيمة {fmt_syp(amount)}.")
    await state.clear()

# قائمة الطلبات المعلقة
@dp.callback_query(F.data == "admin_list_pending")
async def admin_list_pending(c: CallbackQuery):
    if not admin_only(c.from_user.id):
        return await c.answer("ممنوع.", show_alert=True)
    pending = [r for r in DATA["requests"].values() if r["status"] == "pending"]
    if not pending:
        await c.message.edit_text("لا يوجد طلبات معلّقة حاليًا.", reply_markup=admin_panel_kb())
        return await c.answer()
    lines = []
    for r in sorted(pending, key=lambda x: x["created_at"]):
        lines.append(f"{r['id']} | {r['type']} | UID:{r['user_id']} | {time.strftime('%Y-%m-%d %H:%M', time.localtime(r['created_at']))}")
    txt = "الطلبات المعلّقة:\n" + "\n".join(lines) + "\n\nاختر الطلب من رسالة الإشعار الخاصة به للموافقة/الرفض."
    await c.message.edit_text(txt, reply_markup=admin_panel_kb())
    await c.answer()

# موافقة/رفض الطلبات (زرين عامّين)
@dp.callback_query(F.data.startswith("req_ok:"))
async def req_ok(c: CallbackQuery):
    if not admin_only(c.from_user.id):
        return await c.answer("ممنوع.", show_alert=True)
    req_id = c.data.split(":")[1]
    r = get_request(req_id)
    if not r or r["status"] != "pending":
        return await c.answer("طلب غير صالح أو تم التعامل معه.", show_alert=True)
    user_id = r["user_id"]
    u = get_user(user_id)
    if not u:
        set_request_status(req_id, "rejected")
        return await c.answer("المستخدم غير موجود. تم رفض الطلب.", show_alert=True)

# تنفيذ حسب النوع
    t = r["type"]
    p = r["payload"]

    if t == "topup_bot":
        amount = int(p["amount"])
        u["balance"] += amount
        save_data(DATA)
        set_request_status(req_id, "approved")
        try:
            await bot.send_message(user_id, f"✅ تم قبول شحنك بقيمة {fmt_syp(amount)} وإضافته إلى رصيدك.")
        except Exception:
            pass

    elif t == "withdraw_bot":
        amount = int(p["amount"])
        if u["balance"] < amount:
            return await c.answer("رصيد المستخدم غير كافٍ. ارفض الطلب أو اشحن له.", show_alert=True)
        u["balance"] -= amount
        save_data(DATA)
        set_request_status(req_id, "approved")
        try:
            await bot.send_message(user_id, f"✅ تم قبول طلب سحبك بقيمة {fmt_syp(amount)}. سيتم التحويل قريبًا.")
        except Exception:
            pass

    elif t == "create_ichancy":
        # الموافقة تعني: إرسال البيانات للمستخدم وتثبيتها (لكن نحن أصلًا أرسلنا للأدمن للمراجعة)
        ich = {"username": p["username"], "password": p["password"]}
        u["ichancy"] = ich
        save_data(DATA)
        set_request_status(req_id, "approved")
        try:
            await bot.send_message(user_id,
                "✅ تم قبول طلب إنشاء حساب ICHANCY وحفظه:\n"
                f"👤 <code>{escape(ich['username'])}</code>\n"
                f"🔒 <code>{escape(ich['password'])}</code>"
            )
        except Exception:
            pass

    elif t in ("ichancy_topup", "ichancy_withdraw"):
        # عمليات خارجية، فقط إعلام المستخدم
        set_request_status(req_id, "approved")
        action = "شحن حسابك" if t == "ichancy_topup" else "سحب من حسابك"
        try:
            await bot.send_message(user_id, f"✅ تم قبول طلب {action}. سيتم التنفيذ قريبًا.")
        except Exception:
            pass

    else:
        set_request_status(req_id, "approved")

    await c.answer("تمت الموافقة ✔️")

@dp.callback_query(F.data.startswith("req_no:"))
async def req_no(c: CallbackQuery):
    if not admin_only(c.from_user.id):
        return await c.answer("ممنوع.", show_alert=True)
    req_id = c.data.split(":")[1]
    r = get_request(req_id)
    if not r or r["status"] != "pending":
        return await c.answer("طلب غير صالح أو تم التعامل معه.", show_alert=True)
    set_request_status(req_id, "rejected")
    user_id = r["user_id"]
    try:
        await bot.send_message(user_id, "❌ تم رفض طلبك من قبل الأدمن.")
    except Exception:
        pass
    await c.answer("تم الرفض ✖️")

# ------------------ أوامر مساعدة ------------------

@dp.message(Command("balance"))
async def cmd_balance(m: Message):
    u = ensure_user(m.from_user.id, m.from_user.full_name or "")
    await m.answer(f"رصيدك الحالي: <b>{fmt_syp(u['balance'])}</b>")

@dp.message(Command("id"))
async def cmd_id(m: Message):
    await m.answer(f"ID الخاص بك: <code>{m.from_user.id}</code>")

# ------------------ تشغيل البوت ------------------

async def main():
    print("Bot is running...")
    await dp.start_polling(bot)

if name == "main":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
