import asyncio
import logging
import sys
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ===== ТОКЕНЫ =====
BOT_TOKEN = "9000723536:AAGmJnuXkq66ZU3dbOjT03Y83T-YaflKEdc"
XROCKET_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjMxMDkwMSIsImp0aSI6ImFwcDozMTA5MDE6YmFjNmUwNjQtY2UwNi00ZjE0LTkxYmUtZThiNGFmZWRhM2M3IiwiaWF0IjoxNzk1NDc5NTM2fQ.U2uPV6sNohCA_9J7RkE4DWYxwewSKbRo3KChZ0U3928"
CRYPTOBOT_TOKEN = "685556:AASZ3wmOPUPdP7otbBXgHIyshMkUGWN5rKo"
ADMIN_ID = 8827334252
CHANNEL_ID = "@VelsoShopInfo"
SUPPORT_USERNAME = "@velsogod"

URL_OFFER = "https://telegra.ph/Publichnaya-oferta-Velso-Shop-11-23"
URL_RULES = "https://telegra.ph/Pravila-Ispolzovaniya-Velso-Shop-11-24"
URL_PRIVACY = "https://telegra.ph/Politika-konfidencialnosti-Velso-Shop"

dp = Dispatcher(storage=MemoryStorage())

# ===== ПРЕМИУМ-ЭМОДЗИ (работают только если бот Premium) =====
E_CHECK = '<tg-emoji emoji-id="5895514131896733546">✅</tg-emoji>'
E_CROSS = '<tg-emoji emoji-id="5893163582194978381">❌</tg-emoji>'
E_DOLLAR = '<tg-emoji emoji-id="5893473283696759404">💲</tg-emoji>'
E_CLOCK = '<tg-emoji emoji-id="5893102202817352158">⏰</tg-emoji>'
E_EXCL = '<tg-emoji emoji-id="5893072412924187198">❗️</tg-emoji>'
E_WALLET = '<tg-emoji emoji-id="5893255507380014983">👛</tg-emoji>'
E_BOLT = '<tg-emoji emoji-id="5893450623449305489">⚡️</tg-emoji>'
E_PLUS = '<tg-emoji emoji-id="5258108352008823107">➕</tg-emoji>'
E_CATALOG = '<tg-emoji emoji-id="5226513232549664618">🛍</tg-emoji>'
E_LOAD = '<tg-emoji emoji-id="5260687119092817530">⏳</tg-emoji>'
E_REF = '<tg-emoji emoji-id="5258486128742244085">🔗</tg-emoji>'
E_PROFILE = '<tg-emoji emoji-id="5316727448644103237">👤</tg-emoji>'
E_DOTS = '<tg-emoji emoji-id="5429411030960711866">…</tg-emoji>'
E_STATS = '<tg-emoji emoji-id="5258330865674494479">📊</tg-emoji>'
E_SERVICES = '<tg-emoji emoji-id="5260687681733533075">📦</tg-emoji>'
E_BACK = '<tg-emoji emoji-id="5258236805890710909">◀️</tg-emoji>'

DB_PATH = "velso.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        lang TEXT DEFAULT 'ru',
        balance REAL DEFAULT 0,
        accepted INTEGER DEFAULT 0,
        subscribed INTEGER DEFAULT 0,
        referrer_id INTEGER,
        reg_date TEXT,
        status TEXT DEFAULT 'Новичок'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_type TEXT,
        item_name TEXT,
        price REAL,
        status TEXT DEFAULT 'pending',
        reason TEXT,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        name TEXT,
        description TEXT,
        price REAL,
        content TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        amount REAL,
        uses_left INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS order_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        from_user_id INTEGER,
        text TEXT,
        created_at TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def create_user(user_id, referrer_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, referrer_id, reg_date) VALUES (?, ?, ?)",
              (user_id, referrer_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_user(user_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for key, val in kwargs.items():
        c.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (val, user_id))
    conn.commit()
    conn.close()

def add_balance(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def save_order_message(order_id, from_user_id, text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO order_messages (order_id, from_user_id, text, created_at) VALUES (?, ?, ?, ?)",
              (order_id, from_user_id, text, datetime.now().isoformat()))
    conn.commit()
    conn.close()

class States(StatesGroup):
    waiting_amount = State()
    waiting_promocode = State()
    admin_add_item = State()
    admin_add_promo = State()
    admin_broadcast = State()
    order_chat = State()
    admin_reply = State()

TEXTS = {
    "ru": {
        "choose_lang": "🌐 <b>Выбери язык</b> / <i>Choose language</i>:",
        "consent": (
            f"📜 <b>Публичная оферта</b>\n\n"
            f"Используешь бота, приобретаешь услуги — значит согласен с публичной офертой:\n\n"
            f"{E_CHECK} <a href='{URL_PRIVACY}'>Политика конфиденциальности</a>\n\n"
            f"{E_EXCL} <a href='{URL_RULES}'>Правила использования</a>\n\n"
            f"<blockquote>{E_BOLT} Ссылки кликабельны. Нажми «Принимаю», чтобы продолжить.</blockquote>"
        ),
        "accept": f"{E_CHECK} Принимаю",
        "subscribe_text": (
            f"{E_EXCL} <b>Обязательная подписка</b>\n\n"
            f"Для использования бота подпишись на канал:\n\n"
            f"<blockquote>{E_CATALOG} <b>Velso Shop</b> — новости, акции, обновления.</blockquote>\n\n"
            f"После подписки нажми <b>«{E_CHECK} Проверить подписку»</b>."
        ),
        "menu": (
            f"🏠 <b>Меню Velso Shop</b>\n\n"
            f"<blockquote>{E_CATALOG} <b>Каталог</b> — услуги и товары\n"
            f"{E_PROFILE} <b>Профиль</b> — баланс и заказы\n"
            f"{E_REF} <b>Рефералы</b> — 10% с пополнений\n"
            f"📜 <b>Оферта</b> — условия\n"
            f"🆘 <b>Поддержка</b> — связь с нами</blockquote>\n\n"
            f"<i>Выбери раздел ниже 👇</i>"
        ),
        "catalog": (
            f"{E_CATALOG} <b>Каталог</b>\n\n"
            f"<blockquote>{E_SERVICES} <b>Услуги</b> — выполняются вручную\n"
            f"{E_CATALOG} <b>Товар</b> — выдаётся автоматически</blockquote>"
        ),
        "profile_text": (
            f"{E_PROFILE} <b>Профиль</b>\n\n"
            f"<blockquote>🆔 ID: <code>{{user_id}}</code>\n"
            f"{E_WALLET} Баланс: <b>{{balance}} USD</b>\n"
            f"🌐 Язык: {{lang}}\n"
            f"🏆 Статус: <b>{{status}}</b>\n"
            f"📅 Регистрация: {{reg_date}}\n"
            f"{E_REF} Рефералов: <b>{{ref_count}}</b></blockquote>"
        ),
        "ref_text": (
            f"{E_REF} <b>Реферальная система</b>\n\n"
            f"Твоя ссылка:\n<code>{{ref_link}}</code>\n\n"
            f"<blockquote>👥 Приглашено: <b>{{ref_count}}</b>\n"
            f"{E_DOLLAR} Заработано: <b>{{earned}} USD</b> (10% с пополнений рефералов)</blockquote>"
        ),
        "orders_history": f"{E_SERVICES} <b>Мои заказы</b>",
        "no_orders": f"📭 <blockquote>У тебя пока нет заказов.</blockquote>",
        "services_list": f"{E_SERVICES} <b>Услуги:</b>\n\n<blockquote>Выбери услугу и нажми «Купить».</blockquote>",
        "goods_list": f"{E_CATALOG} <b>Товар:</b>\n\n<blockquote>Выбери товар и нажми «Купить». Выдаётся автоматически.</blockquote>",
        "empty_list": f"📭 <blockquote>Пока пусто.</blockquote>",
        "order_created": (
            f"{E_CLOCK} <b>Заказ создан!</b>\n\n"
            f"<blockquote>Ожидай выполнения. Если нужно что-то уточнить — напиши в чат по заказу.</blockquote>"
        ),
        "goods_delivered": f"🎁 <b>Товар выдан:</b>\n\n<blockquote>{{content}}</blockquote>",
        "order_chat_prompt": f"💬 <b>Чат по заказу #{{order_id}}</b>\n\n<blockquote>Напиши сообщение — админ увидит его и ответит.</blockquote>",
        "order_chat_sent": f"{E_CHECK} <blockquote>Сообщение отправлено админу. Ожидай ответа.</blockquote>",
        "admin_panel": f"{E_STATS} <b>Админ-панель</b>",
        "admin_enter_name": "📝 <b>Введи название:</b>",
        "admin_enter_desc": "📝 <b>Введи описание:</b>",
        "admin_enter_price": f"{E_DOLLAR} <b>Введи цену в USD:</b>",
        "admin_enter_content": f"{E_SERVICES} <b>Введи контент (для товара):</b>",
        "admin_item_added": f"{E_CHECK} <b>Добавлено!</b>",
        "admin_no_orders": f"📭 <blockquote>Заказов нет.</blockquote>",
        "admin_reject_reason": "✍️ <b>Введи причину отказа:</b>",
        "admin_stats_text": (
            f"{E_STATS} <b>Статистика</b>\n\n"
            f"<blockquote>👥 Юзеров: <b>{{users}}</b>\n"
            f"{E_SERVICES} Заказов: <b>{{orders}}</b>\n"
            f"{E_DOLLAR} Оборот: <b>{{turnover}} USD</b></blockquote>"
        ),
        "admin_broadcast_text": "📢 <b>Введи текст рассылки:</b>",
        "admin_broadcast_sent": f"{E_CHECK} <blockquote>Отправлено <b>{{count}}</b> юзерам.</blockquote>",
        "admin_promo_code": "🎟 <b>Введи код:</b>",
        "admin_promo_amount": f"{E_DOLLAR} <b>Введи сумму бонуса:</b>",
        "admin_promo_uses": "🔢 <b>Введи кол-во использований:</b>",
        "admin_promo_added": f"{E_CHECK} <b>Промокод добавлен!</b>",
        "promo_enter": "🎟 <b>Введи промокод:</b>",
        "promo_success": f"{E_CHECK} <blockquote>Промокод активирован! <b>+{{amount}} USD</b></blockquote>",
        "promo_invalid": f"{E_CROSS} <blockquote>Неверный или использованный промокод.</blockquote>",
        "order_done_notify": f"{E_CHECK} <b>Твой заказ «{{name}}» выполнен!</b>",
        "order_reject_notify": f"{E_CROSS} <b>Заказ «{{name}}» отклонён.</b>\n\n<blockquote>Причина: {{reason}}</blockquote>",
        "already": f"{E_BOLT} <b>Ты уже принял условия. Добро пожаловать!</b>",
        "insufficient": f"{E_CROSS} <b>Недостаточно средств.</b> Пополни баланс.",
        "enter_amount": f"{E_DOLLAR} <b>Введи сумму в USD для пополнения:</b>",
        "choose_payment": f"{E_WALLET} <b>Выбери способ оплаты:</b>",
        "payment_error": f"{E_CROSS} <b>Ошибка создания счёта.</b> Попробуй позже.",
    }
}

# ===== КЛАВИАТУРЫ (без style — работает на любой aiogram 3.x) =====
def lang_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data="lang:ru")
    kb.button(text="🇬🇧 English", callback_data="lang:en")
    kb.adjust(2)
    return kb.as_markup()

def accept_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принимаю", callback_data="accept")
    return kb.as_markup()

def sub_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Velso Shop", url="https://t.me/VelsoShopInfo")
    kb.button(text="✅ Проверить подписку", callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()

def menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛍 Каталог", callback_data="menu_catalog")
    kb.button(text="👤 Профиль", callback_data="menu_profile")
    kb.button(text="🔗 Рефералы", callback_data="menu_refs")
    kb.button(text="📜 Оферта", url=URL_OFFER)
    kb.button(text="🆘 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME.replace('@','')}")
    kb.adjust(1, 2, 2)
    return kb.as_markup()

def catalog_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 Услуги", callback_data="menu_services")
    kb.button(text="🛍 Товар", callback_data="menu_goods")
    kb.button(text="◀️ Назад", callback_data="back_to_menu")
    kb.adjust(2, 1)
    return kb.as_markup()

def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Назад", callback_data="back_to_menu")
    return kb.as_markup()

def profile_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Пополнить", callback_data="topup")
    kb.button(text="🎟 Промокод", callback_data="promo")
    kb.button(text="📋 Мои заказы", callback_data="my_orders")
    kb.button(text="◀️ Назад", callback_data="back_to_menu")
    kb.adjust(2, 1, 1)
    return kb.as_markup()

def payment_method_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💎 xRocket", callback_data="pay_method:xrocket")
    kb.button(text="🤖 CryptoBot", callback_data="pay_method:cryptobot")
    kb.button(text="❌ Отмена", callback_data="cancel_topup")
    kb.adjust(2, 1)
    return kb.as_markup()

def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Услугу", callback_data="admin_add_service")
    kb.button(text="➕ Товар", callback_data="admin_add_goods")
    kb.button(text="📋 Заказы", callback_data="admin_orders")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.button(text="🎟 Промокоды", callback_data="admin_promo")
    kb.adjust(2, 2, 2)
    return kb.as_markup()

def admin_order_kb(order_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Ответить", callback_data=f"order_reply:{order_id}")
    kb.button(text="✅ Выполнено", callback_data=f"order_done:{order_id}")
    kb.button(text="❌ Не выполнено", callback_data=f"order_reject:{order_id}")
    kb.adjust(1, 2)
    return kb.as_markup()

def order_chat_kb(order_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Написать по заказу", callback_data=f"chat_order:{order_id}")
    kb.button(text="◀️ В каталог", callback_data="menu_catalog")
    kb.adjust(1, 1)
    return kb.as_markup()

async def check_sub(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

async def send_consent(bot: Bot, chat_id: int, lang="ru", edit_message: Message = None):
    try:
        photo = FSInputFile("prav.png")
        await bot.send_photo(chat_id=chat_id, photo=photo,
                             caption=TEXTS[lang]["consent"], reply_markup=accept_kb())
        if edit_message:
            await edit_message.delete()
    except Exception:
        if edit_message:
            await edit_message.edit_text(TEXTS[lang]["consent"], reply_markup=accept_kb(), disable_web_page_preview=True)
        else:
            await bot.send_message(chat_id, TEXTS[lang]["consent"], reply_markup=accept_kb(), disable_web_page_preview=True)

async def send_subscribe(bot: Bot, chat_id: int, lang="ru", edit_message: Message = None):
    try:
        photo = FSInputFile("podp.png")
        await bot.send_photo(chat_id=chat_id, photo=photo,
                             caption=TEXTS[lang]["subscribe_text"], reply_markup=sub_kb())
        if edit_message:
            await edit_message.delete()
    except Exception:
        if edit_message:
            await edit_message.edit_text(TEXTS[lang]["subscribe_text"], reply_markup=sub_kb())
        else:
            await bot.send_message(chat_id, TEXTS[lang]["subscribe_text"], reply_markup=sub_kb())

async def send_menu(bot: Bot, chat_id: int, lang="ru", edit_message: Message = None):
    try:
        photo = FSInputFile("main.png")
        await bot.send_photo(chat_id=chat_id, photo=photo,
                             caption=TEXTS[lang]["menu"], reply_markup=menu_kb())
        if edit_message:
            await edit_message.delete()
    except Exception:
        if edit_message:
            await edit_message.edit_text(TEXTS[lang]["menu"], reply_markup=menu_kb())
        else:
            await bot.send_message(chat_id, TEXTS[lang]["menu"], reply_markup=menu_kb())

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    uid = message.from_user.id
    user = get_user(uid)
    if not user:
        args = message.text.split()
        referrer_id = None
        if len(args) > 1 and args[1].startswith("ref_"):
            try:
                referrer_id = int(args[1].replace("ref_", ""))
            except:
                pass
        create_user(uid, referrer_id)
        user = get_user(uid)
    if user[4]:
        if await check_sub(message.bot, uid):
            update_user(uid, subscribed=1)
            await send_menu(message.bot, message.chat.id, user[1])
        else:
            await send_subscribe(message.bot, message.chat.id, user[1])
        return
    await message.answer(TEXTS["ru"]["choose_lang"], reply_markup=lang_kb())

@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    update_user(callback.from_user.id, lang=lang)
    await send_consent(callback.bot, callback.from_user.id, lang, edit_message=callback.message)
    await callback.answer()

@dp.callback_query(F.data == "accept")
async def on_accept(callback: CallbackQuery):
    uid = callback.from_user.id
    update_user(uid, accepted=1)
    user = get_user(uid)
    lang = user[1] if user else "ru"
    await callback.message.delete()
    await send_subscribe(callback.bot, callback.from_user.id, lang)
    await callback.answer()

@dp.callback_query(F.data == "check_sub")
async def on_check_sub(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    if await check_sub(callback.bot, uid):
        update_user(uid, subscribed=1)
        await callback.message.delete()
        await send_menu(callback.bot, callback.from_user.id, lang)
        await callback.answer("✅ Подписка подтверждена!")
    else:
        await callback.answer("❌ Ты ещё не подписался.", show_alert=True)

@dp.callback_query(F.data == "back_to_menu")
async def on_back(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user[1] if user else "ru"
    await callback.message.delete()
    await send_menu(callback.bot, callback.from_user.id, lang)
    await callback.answer()

@dp.callback_query(F.data == "menu_catalog")
async def on_catalog(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user[1] if user else "ru"
    await callback.message.delete()
    await callback.message.answer(TEXTS[lang]["catalog"], reply_markup=catalog_kb())
    await callback.answer()

# ===== ПРОФИЛЬ — исправлен: edit_text вместо delete+answer =====
@dp.callback_query(F.data == "menu_profile")
async def on_profile(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (uid,))
    ref_count = c.fetchone()[0]
    conn.close()
    text = TEXTS[lang]["profile_text"].format(
        user_id=uid, balance=user[2], lang=user[1],
        status=user[7] or "Новичок",
        reg_date=user[6][:10] if user[6] else "—",
        ref_count=ref_count
    )
    try:
        await callback.message.edit_text(text, reply_markup=profile_kb())
    except Exception as e:
        logging.error(f"profile error: {e}")
        await callback.answer("Ошибка профиля. Смотри логи.", show_alert=True)
        return
    await callback.answer()

@dp.callback_query(F.data == "topup")
async def on_topup(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user[1] if user else "ru"
    await state.set_state(States.waiting_amount)
    await callback.message.edit_text(TEXTS[lang]["enter_amount"], reply_markup=back_kb())
    await callback.answer()

@dp.message(States.waiting_amount)
async def on_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except:
        await message.answer(f"{E_CROSS} <b>Введи корректную сумму</b> (число больше 0):")
        return
    await state.update_data(amount=amount)
    user = get_user(message.from_user.id)
    lang = user[1] if user else "ru"
    await message.answer(
        f"{E_DOLLAR} <b>Сумма:</b> {amount} USD\n\n{TEXTS[lang]['choose_payment']}",
        reply_markup=payment_method_kb()
    )

# ===== XROCKET — исправлено: currency передаётся, get_invoice для проверки =====
@dp.callback_query(F.data.startswith("pay_method:"))
async def on_pay_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split(":")[1]
    data = await state.get_data()
    amount = data.get("amount", 0)
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"

    if method == "xrocket":
        try:
            from aiorocket2 import xRocketClient
            client = xRocketClient(api_key=XROCKET_TOKEN)
            invoice = await client.create_invoice(
                currency="USDT",
                amount=amount,
                min_payment=0,
                num_payments=1,
                description=f"Пополнение Velso Shop на {amount} USD",
                hidden_message="Спасибо за оплату!"
            )
            link = invoice.link
            invoice_id = invoice.id
            await state.update_data(xrocket_invoice_id=invoice_id, xrocket_amount=amount)

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к оплате", url=link)],
                [InlineKeyboardButton(text="✅ Проверить оплату", callback_data="check_xrocket_pay")]
            ])
            await callback.message.edit_text(
                f"{E_DOLLAR} <b>Сумма:</b> {amount} USD\n\n"
                f"{E_WALLET} Нажми «Перейти к оплате», оплати счёт, затем нажми «Проверить оплату».",
                reply_markup=kb
            )
        except Exception as e:
            logging.error(f"xRocket create invoice error: {e}")
            await callback.message.edit_text(TEXTS[lang]["payment_error"])
        await callback.answer()
        return

    if method == "cryptobot":
        try:
            from async_crypto_pay_api import CryptoPayApi
            from async_crypto_pay_api.models import CurrencyType, FiatAsset
            crypto = CryptoPayApi(CRYPTOBOT_TOKEN)
            async with crypto:
                invoice = await crypto.create_invoice(
                    currency_type=CurrencyType.FIAT, fiat=FiatAsset.USD,
                    amount=amount,
                    description=f"Пополнение Velso Shop на {amount} USD"
                )
                link = invoice.bot_invoice_url
            await callback.message.edit_text(
                f"{E_CHECK} <b>Счёт создан!</b> Перейди по ссылке для оплаты:\n{link}",
                disable_web_page_preview=True
            )
            await state.clear()
        except Exception as e:
            logging.error(f"CryptoBot error: {e}")
            await callback.message.edit_text(TEXTS[lang]["payment_error"])
        await callback.answer()
        return

@dp.callback_query(F.data == "check_xrocket_pay")
async def on_check_xrocket_pay(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    invoice_id = data.get("xrocket_invoice_id")
    amount = data.get("xrocket_amount", 0)
    uid = callback.from_user.id

    if not invoice_id:
        await callback.answer("Счёт не найден. Создай заново.", show_alert=True)
        return

    try:
        from aiorocket2 import xRocketClient
        client = xRocketClient(api_key=XROCKET_TOKEN)
        invoice = await client.get_invoice(invoice_id=invoice_id)

        if invoice.status == "paid":
            add_balance(uid, amount)
            await state.clear()
            await callback.message.edit_text(
                f"{E_CHECK} <b>Оплата подтверждена!</b>\n\n"
                f"{E_WALLET} Баланс пополнен на <b>{amount} USD</b>."
            )
            await callback.answer("✅ Баланс пополнен!")
        elif invoice.status == "active":
            await callback.answer("⏳ Оплата ещё не поступила. Попробуй через минуту.", show_alert=True)
        else:
            await callback.answer(f"Статус счёта: {invoice.status}. Попробуй позже.", show_alert=True)
    except Exception as e:
        logging.error(f"xRocket check error: {e}")
        await callback.answer("Ошибка проверки. Попробуй позже.", show_alert=True)

@dp.callback_query(F.data == "cancel_topup")
async def on_cancel_topup(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    lang = user[1] if user else "ru"
    await callback.message.delete()
    await send_menu(callback.bot, callback.from_user.id, lang)
    await callback.answer()

@dp.callback_query(F.data == "menu_refs")
async def on_refs(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (uid,))
    ref_count = c.fetchone()[0]
    conn.close()
    ref_link = f"https://t.me/VelsoShopBot?start=ref_{uid}"
    earned = ref_count * 0
    text = TEXTS[lang]["ref_text"].format(ref_link=ref_link, ref_count=ref_count, earned=earned)
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "menu_services")
async def on_services(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user[1] if user else "ru"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM items WHERE type = 'service'")
    items = c.fetchall()
    conn.close()
    if not items:
        await callback.message.edit_text(TEXTS[lang]["empty_list"], reply_markup=catalog_kb())
    else:
        kb = InlineKeyboardBuilder()
        text = TEXTS[lang]["services_list"] + "\n\n"
        for item in items:
            text += f"• <b>{item[1]}</b> — {item[2]} USD\n"
            kb.button(text=f"🛒 Купить «{item[1]}»", callback_data=f"buy:service:{item[0]}")
        kb.button(text="◀️ Назад", callback_data="menu_catalog")
        kb.adjust(1)
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "menu_goods")
async def on_goods(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user[1] if user else "ru"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM items WHERE type = 'goods'")
    items = c.fetchall()
    conn.close()
    if not items:
        await callback.message.edit_text(TEXTS[lang]["empty_list"], reply_markup=catalog_kb())
    else:
        kb = InlineKeyboardBuilder()
        text = TEXTS[lang]["goods_list"] + "\n\n"
        for item in items:
            text += f"• <b>{item[1]}</b> — {item[2]} USD\n"
            kb.button(text=f"🛒 Купить «{item[1]}»", callback_data=f"buy:goods:{item[0]}")
        kb.button(text="◀️ Назад", callback_data="menu_catalog")
        kb.adjust(1)
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("buy:"))
async def on_buy(callback: CallbackQuery):
    _, item_type, item_id = callback.data.split(":")
    item_id = int(item_id)
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, price, content FROM items WHERE id = ?", (item_id,))
    item = c.fetchone()
    conn.close()
    if not item:
        await callback.answer("Товар не найден", show_alert=True)
        return
    name, price, content = item
    if user[2] < price:
        await callback.answer(TEXTS[lang]["insufficient"], show_alert=True)
        return
    add_balance(uid, -price)
    if item_type == "goods":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO orders (user_id, item_type, item_name, price, status, created_at) VALUES (?, ?, ?, ?, 'completed', ?)",
                  (uid, item_type, name, price, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        await callback.message.edit_text(TEXTS[lang]["goods_delivered"].format(content=content), reply_markup=catalog_kb())
    else:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO orders (user_id, item_type, item_name, price, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                  (uid, item_type, name, price, datetime.now().isoformat()))
        order_id = c.lastrowid
        conn.commit()
        conn.close()
        try:
            await callback.bot.send_message(
                ADMIN_ID,
                f"{E_PLUS} <b>Новый заказ #{order_id}</b>\n\n"
                f"<blockquote>{E_PROFILE} Юзер: <code>{uid}</code>\n"
                f"{E_SERVICES} Услуга: <b>{name}</b>\n"
                f"{E_DOLLAR} Цена: <b>{price} USD</b></blockquote>",
                reply_markup=admin_order_kb(order_id)
            )
        except:
            pass
        await callback.message.edit_text(
            TEXTS[lang]["order_created"] + f"\n\n{E_DOTS} Заказ: <b>#{order_id}</b>",
            reply_markup=order_chat_kb(order_id)
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("chat_order:"))
async def on_chat_order(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    user = get_user(callback.from_user.id)
    lang = user[1] if user else "ru"
    await state.set_state(States.order_chat)
    await state.update_data(order_id=order_id)
    await callback.message.edit_text(
        TEXTS[lang]["order_chat_prompt"].format(order_id=order_id),
        reply_markup=back_kb()
    )
    await callback.answer()

@dp.message(States.order_chat)
async def on_order_chat_message(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    uid = message.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    text = message.text
    save_order_message(order_id, uid, text)
    try:
        await message.bot.send_message(
            ADMIN_ID,
            f"💬 <b>Сообщение по заказу #{order_id}</b>\n\n"
            f"<blockquote>{E_PROFILE} От: <code>{uid}</code>\n"
            f"📝 {text}</blockquote>",
            reply_markup=admin_order_kb(order_id)
        )
    except:
        pass
    await message.answer(TEXTS[lang]["order_chat_sent"], reply_markup=back_kb())
    await state.clear()

@dp.callback_query(F.data.startswith("order_reply:"))
async def on_order_reply(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    order_id = int(callback.data.split(":")[1])
    await state.set_state(States.admin_reply)
    await state.update_data(reply_order_id=order_id)
    await callback.message.edit_text(f"💬 <b>Ответ по заказу #{order_id}</b>\n\nНапиши текст ответа:")
    await callback.answer()

@dp.message(States.admin_reply)
async def on_admin_reply(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    order_id = data.get("reply_order_id")
    text = message.text
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
    row = c.fetchone()
    conn.close()
    if row:
        uid = row[0]
        save_order_message(order_id, ADMIN_ID, text)
        try:
            await message.bot.send_message(
                uid,
                f"💬 <b>Ответ по заказу #{order_id}</b>\n\n"
                f"<blockquote>📝 {text}</blockquote>",
                reply_markup=order_chat_kb(order_id)
            )
        except:
            pass
        await message.answer(f"{E_CHECK} Ответ отправлен юзеру по заказу #{order_id}.")
    else:
        await message.answer(f"{E_CROSS} Заказ не найден.")
    await state.clear()

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(TEXTS["ru"]["admin_panel"], reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_add_service")
async def admin_add_service(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(States.admin_add_item)
    await state.update_data(item_type="service", step="name")
    await callback.message.edit_text(TEXTS["ru"]["admin_enter_name"])
    await callback.answer()

@dp.callback_query(F.data == "admin_add_goods")
async def admin_add_goods(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(States.admin_add_item)
    await state.update_data(item_type="goods", step="name")
    await callback.message.edit_text(TEXTS["ru"]["admin_enter_name"])
    await callback.answer()

@dp.message(States.admin_add_item)
async def admin_item_step(message: Message, state: FSMContext):
    data = await state.get_data()
    step = data.get("step", "name")
    if step == "reject_reason":
        order_id = data.get("reject_order_id")
        reason = message.text
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id, item_name, price FROM orders WHERE id = ?", (order_id,))
        order = c.fetchone()
        c.execute("UPDATE orders SET status = 'rejected', reason = ? WHERE id = ?", (reason, order_id))
        conn.commit()
        conn.close()
        if order:
            add_balance(order[0], order[2])
            try:
                await message.bot.send_message(
                    order[0],
                    TEXTS["ru"]["order_reject_notify"].format(name=order[1], reason=reason)
                )
            except:
                pass
        await state.clear()
        await message.answer(f"{E_CROSS} Заказ #{order_id} отклонён. Причина: {reason}")
        return
    if step == "name":
        await state.update_data(name=message.text, step="desc")
        await message.answer(TEXTS["ru"]["admin_enter_desc"])
    elif step == "desc":
        await state.update_data(desc=message.text, step="price")
        await message.answer(TEXTS["ru"]["admin_enter_price"])
    elif step == "price":
        try:
            price = float(message.text.replace(",", "."))
        except:
            await message.answer(f"{E_CROSS} Введи число:")
            return
        await state.update_data(price=price, step="content")
        await message.answer(TEXTS["ru"]["admin_enter_content"])
    elif step == "content":
        content = message.text
        data = await state.get_data()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO items (type, name, description, price, content) VALUES (?, ?, ?, ?, ?)",
                  (data["item_type"], data["name"], data["desc"], data["price"], content))
        conn.commit()
        conn.close()
        await state.clear()
        await message.answer(TEXTS["ru"]["admin_item_added"])

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, user_id, item_name, price, status FROM orders WHERE status = 'pending' ORDER BY id DESC")
    orders = c.fetchall()
    conn.close()
    if not orders:
        await callback.message.edit_text(TEXTS["ru"]["admin_no_orders"], reply_markup=back_kb())
    else:
        text = f"{E_SERVICES} <b>Заказы в ожидании:</b>\n\n"
        for o in orders:
            text += f"#{o[0]} | {o[1]} | {o[2]} | {o[3]} USD\n"
        for o in orders:
            await callback.bot.send_message(
                ADMIN_ID,
                f"{E_SERVICES} <b>Заказ #{o[0]}</b>\n\n"
                f"<blockquote>{E_PROFILE} Юзер: <code>{o[1]}</code>\n"
                f"{E_CATALOG} Товар: <b>{o[2]}</b>\n"
                f"{E_DOLLAR} Цена: <b>{o[3]} USD</b></blockquote>",
                reply_markup=admin_order_kb(o[0])
            )
        await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data.startswith("order_done:"))
async def order_done(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    order_id = int(callback.data.split(":")[1])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, item_name FROM orders WHERE id = ?", (order_id,))
    order = c.fetchone()
    c.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    if order:
        try:
            await callback.bot.send_message(
                order[0],
                TEXTS["ru"]["order_done_notify"].format(name=order[1])
            )
        except:
            pass
    await callback.message.edit_text(f"{E_CHECK} Заказ #{order_id} выполнен.")
    await callback.answer()

@dp.callback_query(F.data.startswith("order_reject:"))
async def order_reject(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    order_id = int(callback.data.split(":")[1])
    await state.set_state(States.admin_add_item)
    await state.update_data(step="reject_reason", reject_order_id=order_id)
    await callback.message.edit_text(TEXTS["ru"]["admin_reject_reason"])
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders")
    orders = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(price), 0) FROM orders WHERE status = 'completed'")
    turnover = c.fetchone()[0]
    conn.close()
    text = TEXTS["ru"]["admin_stats_text"].format(users=users, orders=orders, turnover=turnover)
    await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(States.admin_broadcast)
    await callback.message.edit_text(TEXTS["ru"]["admin_broadcast_text"])
    await callback.answer()

@dp.message(States.admin_broadcast)
async def do_broadcast(message: Message, state: FSMContext):
    text = message.text
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    sent = 0
    for u in users:
        try:
            await message.bot.send_message(u[0], text)
            sent += 1
        except:
            pass
    await state.clear()
    await message.answer(TEXTS["ru"]["admin_broadcast_sent"].format(count=sent))

@dp.callback_query(F.data == "admin_promo")
async def admin_promo(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(States.admin_add_promo)
    await state.update_data(step="code")
    await callback.message.edit_text(TEXTS["ru"]["admin_promo_code"])
    await callback.answer()

@dp.message(States.admin_add_promo)
async def admin_promo_step(message: Message, state: FSMContext):
    data = await state.get_data()
    step = data.get("step", "code")
    if step == "code":
        await state.update_data(code=message.text, step="amount")
        await message.answer(TEXTS["ru"]["admin_promo_amount"])
    elif step == "amount":
        try:
            amount = float(message.text.replace(",", "."))
        except:
            await message.answer(f"{E_CROSS} Введи число:")
            return
        await state.update_data(amount=amount, step="uses")
        await message.answer(TEXTS["ru"]["admin_promo_uses"])
    elif step == "uses":
        try:
            uses = int(message.text)
        except:
            await message.answer(f"{E_CROSS} Введи целое число:")
            return
        data = await state.get_data()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO promocodes (code, amount, uses_left) VALUES (?, ?, ?)",
                  (data["code"], data["amount"], uses))
        conn.commit()
        conn.close()
        await state.clear()
        await message.answer(TEXTS["ru"]["admin_promo_added"])

@dp.callback_query(F.data == "promo")
async def on_promo(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user[1] if user else "ru"
    await state.set_state(States.waiting_promocode)
    await callback.message.edit_text(TEXTS[lang]["promo_enter"], reply_markup=back_kb())
    await callback.answer()

@dp.message(States.waiting_promocode)
async def apply_promo(message: Message, state: FSMContext):
    code = message.text.strip()
    uid = message.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT amount, uses_left FROM promocodes WHERE code = ? AND uses_left > 0", (code,))
    promo = c.fetchone()
    if promo:
        amount, uses = promo
        c.execute("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        add_balance(uid, amount)
        await message.answer(TEXTS[lang]["promo_success"].format(amount=amount), reply_markup=back_kb())
    else:
        conn.close()
        await message.answer(TEXTS[lang]["promo_invalid"], reply_markup=back_kb())
    await state.clear()

@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT item_name, price, status, created_at FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 20", (uid,))
    orders = c.fetchall()
    conn.close()
    if not orders:
        await callback.message.edit_text(TEXTS[lang]["no_orders"], reply_markup=back_kb())
    else:
        text = TEXTS[lang]["orders_history"] + "\n\n"
        status_map = {"pending": f"{E_CLOCK} В обработке", "completed": f"{E_CHECK} Выполнено", "rejected": f"{E_CROSS} Отклонено"}
        for o in orders:
            text += f"• <b>{o[0]}</b> — {o[1]} USD — {status_map.get(o[2], o[2])} ({o[3][:10]})\n"
        await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())