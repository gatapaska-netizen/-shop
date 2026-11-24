import asyncio
import logging
import os
import sys
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    PreCheckoutQuery, LabeledPrice, FSInputFile
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

# ===== ДИСПЕТЧЕР =====
dp = Dispatcher(storage=MemoryStorage())

# ===== БАЗА ДАННЫХ =====
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

# ===== СОСТОЯНИЯ =====
class States(StatesGroup):
    waiting_amount = State()
    waiting_promocode = State()
    admin_add_item = State()
    admin_add_promo = State()
    admin_broadcast = State()
    order_chat = State()          # юзер пишет в чат заказа
    admin_reply = State()         # админ отвечает по заказу

# ===== ТЕКСТЫ (с жирным и цитатами) =====
TEXTS = {
    "ru": {
        "choose_lang": "🌐 <b>Выбери язык</b> / <i>Choose language</i>:",
        "consent": (
            "📜 <b>Публичная оферта</b>\n\n"
            "Используешь бота, приобретаешь услуги — значит согласен с публичной офертой:\n\n"
            f"✅ <a href='{URL_PRIVACY}'>Политика конфиденциальности</a>\n\n"
            f"❗️<a href='{URL_RULES}'>Правила использования</a>\n\n"
            "<blockquote>🔗 Ссылки кликабельны. Нажми «Принимаю», чтобы продолжить.</blockquote>"
        ),
        "accept": "✅ Принимаю",
        "subscribe_text": (
            "📢 <b>Обязательная подписка</b>\n\n"
            "Для использования бота подпишись на канал:\n\n"
            "<blockquote>🛒 <b>Velso Shop</b> — новости, акции, обновления.</blockquote>\n\n"
            "После подписки нажми <b>«✅ Проверить подписку»</b>."
        ),
        "menu": (
            "🏠 <b>Меню</b>\n\n"
            "<blockquote>🛍 Каталог — услуги и товары\n"
            "👤 Профиль — баланс и заказы\n"
            "🔗 Рефералы — 10% с пополнений\n"
            "📜 Оферта — условия\n"
            "🆘 Поддержка — связь с нами</blockquote>"
        ),
        "catalog": "🛍 <b>Каталог</b>\n\n<blockquote>Выбери раздел:</blockquote>",
        "profile_text": (
            "👤 <b>Профиль</b>\n\n"
            "<blockquote>🆔 ID: <code>{user_id}</code>\n"
            "💰 Баланс: <b>{balance} USD</b>\n"
            "🌐 Язык: {lang}\n"
            "🏆 Статус: <b>{status}</b>\n"
            "📅 Дата регистрации: {reg_date}\n"
            "👥 Рефералов: {ref_count}</blockquote>"
        ),
        "ref_text": (
            "🔗 <b>Реферальная система</b>\n\n"
            "Твоя ссылка:\n<code>{ref_link}</code>\n\n"
            "<blockquote>👥 Приглашено: <b>{ref_count}</b>\n"
            "💰 Заработано: <b>{earned} USD</b> (10% с пополнений рефералов)</blockquote>"
        ),
        "orders_history": "📋 <b>Мои заказы</b>",
        "no_orders": "📭 <blockquote>У тебя пока нет заказов.</blockquote>",
        "services_list": "📦 <b>Услуги:</b>\n\n<blockquote>Выбери услугу и нажми «Купить».</blockquote>",
        "goods_list": "🛍 <b>Товар:</b>\n\n<blockquote>Выбери товар и нажми «Купить». Выдаётся автоматически.</blockquote>",
        "empty_list": "📭 <blockquote>Пока пусто.</blockquote>",
        "order_created": (
            "⏳ <b>Заказ создан!</b>\n\n"
            "<blockquote>Ожидай выполнения. Если нужно что-то уточнить — напиши в чат по заказу.</blockquote>"
        ),
        "goods_delivered": "🎁 <b>Товар выдан:</b>\n\n<blockquote>{content}</blockquote>",
        "order_chat_prompt": "💬 <b>Чат по заказу #{order_id}</b>\n\n<blockquote>Напиши сообщение — админ увидит его и ответит.</blockquote>",
        "order_chat_sent": "✅ <blockquote>Сообщение отправлено админу. Ожидай ответа.</blockquote>",
        "admin_panel": "⚙️ <b>Админ-панель</b>",
        "admin_enter_name": "📝 <b>Введи название:</b>",
        "admin_enter_desc": "📝 <b>Введи описание:</b>",
        "admin_enter_price": "💵 <b>Введи цену в USD:</b>",
        "admin_enter_content": "📦 <b>Введи контент (для товара):</b>",
        "admin_item_added": "✅ <b>Добавлено!</b>",
        "admin_no_orders": "📭 <blockquote>Заказов нет.</blockquote>",
        "admin_reject_reason": "✍️ <b>Введи причину отказа:</b>",
        "admin_stats_text": (
            "📊 <b>Статистика</b>\n\n"
            "<blockquote>👥 Юзеров: <b>{users}</b>\n"
            "📦 Заказов: <b>{orders}</b>\n"
            "💰 Оборот: <b>{turnover} USD</b></blockquote>"
        ),
        "admin_broadcast_text": "📢 <b>Введи текст рассылки:</b>",
        "admin_broadcast_sent": "✅ <blockquote>Отправлено <b>{count}</b> юзерам.</blockquote>",
        "admin_promo_code": "🎟 <b>Введи код:</b>",
        "admin_promo_amount": "💰 <b>Введи сумму бонуса:</b>",
        "admin_promo_uses": "🔢 <b>Введи кол-во использований:</b>",
        "admin_promo_added": "✅ <b>Промокод добавлен!</b>",
        "promo_enter": "🎟 <b>Введи промокод:</b>",
        "promo_success": "✅ <blockquote>Промокод активирован! <b>+{amount} USD</b></blockquote>",
        "promo_invalid": "❌ <blockquote>Неверный или использованный промокод.</blockquote>",
        "order_done_notify": "✅ <b>Твой заказ «{name}» выполнен!</b>",
        "order_reject_notify": "❌ <b>Заказ «{name}» отклонён.</b>\n\n<blockquote>Причина: {reason}</blockquote>",
        "already": "🚀 <b>Ты уже принял условия. Добро пожаловать!</b>",
    }
}

# ===== КЛАВИАТУРЫ =====
def lang_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data="lang:ru")
    kb.button(text="🇬🇧 English", callback_data="lang:en")
    kb.adjust(2)
    return kb.as_markup()

def accept_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принимаю", callback_data="accept", style="success")
    return kb.as_markup()

def sub_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Velso Shop", url="https://t.me/VelsoShopInfo", style="primary")
    kb.button(text="✅ Проверить подписку", callback_data="check_sub", style="success")
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
    kb.button(text="💰 Пополнить", callback_data="topup", style="success")
    kb.button(text="🎟 Промокод", callback_data="promo")
    kb.button(text="📋 Мои заказы", callback_data="my_orders")
    kb.button(text="◀️ Назад", callback_data="back_to_menu")
    kb.adjust(2, 1, 1)
    return kb.as_markup()

def payment_method_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💎 xRocket", callback_data="pay_method:xrocket")
    kb.button(text="🤖 CryptoBot", callback_data="pay_method:cryptobot")
    kb.button(text="❌ Отмена", callback_data="cancel_topup", style="danger")
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
    """Кнопки для админа по заказу: ответить, выполнено, не выполнено"""
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Ответить", callback_data=f"order_reply:{order_id}", style="primary")
    kb.button(text="✅ Выполнено", callback_data=f"order_done:{order_id}", style="success")
    kb.button(text="❌ Не выполнено", callback_data=f"order_reject:{order_id}", style="danger")
    kb.adjust(1, 2)
    return kb.as_markup()

def order_chat_kb(order_id):
    """Кнопка для юзера — написать в чат заказа"""
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Написать по заказу", callback_data=f"chat_order:{order_id}", style="primary")
    kb.button(text="◀️ В каталог", callback_data="menu_catalog")
    kb.adjust(1, 1)
    return kb.as_markup()

# ===== ХЕЛПЕРЫ =====
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

# ===== ХЕНДЛЕРЫ =====

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

    if user[4]:  # accepted
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
    uid = callback.from_user.id
    update_user(uid, lang=lang)
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
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    await callback.message.delete()
    await send_menu(callback.bot, callback.from_user.id, lang)
    await callback.answer()

# ===== КАТАЛОГ =====
@dp.callback_query(F.data == "menu_catalog")
async def on_catalog(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user[1] if user else "ru"
    await callback.message.edit_text(TEXTS[lang]["catalog"], reply_markup=catalog_kb())
    await callback.answer()

# ===== ПРОФИЛЬ =====
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
    await callback.message.edit_text(text, reply_markup=profile_kb())
    await callback.answer()

# ===== ПОПОЛНЕНИЕ =====
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
        await message.answer("⚠️ <b>Введи корректную сумму</b> (число больше 0):")
        return
    await state.update_data(amount=amount)
    user = get_user(message.from_user.id)
    lang = user[1] if user else "ru"
    await message.answer(
        f"💵 <b>Сумма:</b> {amount} USD\n\n{TEXTS[lang]['choose_payment']}",
        reply_markup=payment_method_kb()
    )

@dp.callback_query(F.data.startswith("pay_method:"))
async def on_pay_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split(":")[1]
    data = await state.get_data()
    amount = data.get("amount", 0)
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    try:
        if method == "xrocket":
            from aiorocket2 import xRocketClient
            client = xRocketClient(api_key=XROCKET_TOKEN)
            invoice = await client.create_invoice(
                amount=amount, min_payment=0, num_payments=1,
                description=f"Пополнение Velso Shop на {amount} USD",
                hidden_message="Спасибо за оплату!"
            )
            link = invoice.link
        elif method == "cryptobot":
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
        else:
            return
        await callback.message.edit_text(
            TEXTS[lang]["invoice_created"].format(link=link),
            disable_web_page_preview=True
        )
        await state.clear()
    except Exception as e:
        logging.error(f"Payment error: {e}")
        await callback.message.edit_text(TEXTS[lang]["payment_error"])
    await callback.answer()

@dp.callback_query(F.data == "cancel_topup")
async def on_cancel_topup(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    lang = user[1] if user else "ru"
    await callback.message.delete()
    await send_menu(callback.bot, callback.from_user.id, lang)
    await callback.answer()

# ===== РЕФЕРАЛЫ =====
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
    await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()

# ===== УСЛУГИ / ТОВАР =====
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
        await callback.answer("❌ Недостаточно средств. Пополни баланс.", show_alert=True)
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
                f"🆕 <b>Новый заказ #{order_id}</b>\n\n"
                f"<blockquote>👤 Юзер: <code>{uid}</code>\n"
                f"📦 Услуга: <b>{name}</b>\n"
                f"💰 Цена: <b>{price} USD</b></blockquote>\n\n"
                f"Нажми «💬 Ответить», чтобы написать юзеру.",
                reply_markup=admin_order_kb(order_id)
            )
        except:
            pass
        await callback.message.edit_text(
            TEXTS[lang]["order_created"] + f"\n\n🆔 Заказ: <b>#{order_id}</b>",
            reply_markup=order_chat_kb(order_id)
        )
    await callback.answer()

# ===== ЧАТ ПО ЗАКАЗУ (ЮЗЕР) =====
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

    # Пересылаем админу
    try:
        await message.bot.send_message(
            ADMIN_ID,
            f"💬 <b>Сообщение по заказу #{order_id}</b>\n\n"
            f"<blockquote>👤 От: <code>{uid}</code>\n"
            f"📝 {text}</blockquote>",
            reply_markup=admin_order_kb(order_id)
        )
    except:
        pass

    await message.answer(TEXTS[lang]["order_chat_sent"], reply_markup=back_kb())
    await state.clear()

# ===== ОТВЕТ АДМИНА ПО ЗАКАЗУ =====
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
        await message.answer(f"✅ Ответ отправлен юзеру по заказу #{order_id}.")
    else:
        await message.answer("❌ Заказ не найден.")
    await state.clear()

# ===== АДМИНКА =====
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
        await message.answer(f"❌ Заказ #{order_id} отклонён. Причина: {reason}")
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
            await message.answer("⚠️ Введи число:")
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
        text = "📋 <b>Заказы в ожидании:</b>\n\n"
        for o in orders:
            text += f"#{o[0]} | {o[1]} | {o[2]} | {o[3]} USD\n"
        for o in orders:
            await callback.bot.send_message(
                ADMIN_ID,
                f"📋 <b>Заказ #{o[0]}</b>\n\n"
                f"<blockquote>👤 Юзер: <code>{o[1]}</code>\n"
                f"📦 Товар: <b>{o[2]}</b>\n"
                f"💰 Цена: <b>{o[3]} USD</b></blockquote>",
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
    await callback.message.edit_text(f"✅ Заказ #{order_id} выполнен.")
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
            await message.answer("⚠️ Введи число:")
            return
        await state.update_data(amount=amount, step="uses")
        await message.answer(TEXTS["ru"]["admin_promo_uses"])
    elif step == "uses":
        try:
            uses = int(message.text)
        except:
            await message.answer("⚠️ Введи целое число:")
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

# ===== ПРОМОКОД =====
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

# ===== ИСТОРИЯ ЗАКАЗОВ =====
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
        status_map = {"pending": "⏳ В обработке", "completed": "✅ Выполнено", "rejected": "❌ Отклонено"}
        for o in orders:
            text += f"• <b>{o[0]}</b> — {o[1]} USD — {status_map.get(o[2], o[2])} ({o[3][:10]})\n"
        await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()

# ===== ЗАПУСК =====
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())