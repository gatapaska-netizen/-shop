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
    PreCheckoutQuery, LabeledPrice
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ===== ТОКЕНЫ (вставь свои) =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "9000723536:AAGmJnuXkq66ZU3dbOjT03Y83T-YaflKEdc")
XROCKET_TOKEN = os.getenv("XROCKET_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjMxMDkwMSIsImp0aSI6ImFwcDozMTA5MDE6YmFjNmUwNjQtY2UwNi00ZjE0LTkxYmUtZThiNGFmZWRhM2M3IiwiaWF0IjoxNzk1NDc5NTM2fQ.U2uPV6sNohCA_9J7RkE4DWYxwewSKbRo3KChZ0U3928")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "685556:AASZ3wmOPUPdP7otbBXgHIyshMkUGWN5rKo")
ADMIN_ID = 8827334252
CHANNEL_ID = "@VelsoShopInfo"
SUPPORT_USERNAME = "@velsogod"

URL_OFFER = "https://telegra.ph/Publichnaya-oferta-Velso-Shop-11-23"
URL_RULES = "https://telegra.ph/Pravila-Ispolzovaniya-Velso-Shop-11-24"
URL_PRIVACY = "https://telegra.ph/Politika-konfidencialnosti-Velso-Shop"  # заглушка, замени когда будет

# ===== БАЗА ДАННЫХ (SQLite) =====
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

# ===== СОСТОЯНИЯ FSM =====
class States(StatesGroup):
    waiting_amount = State()
    waiting_promocode = State()
    admin_add_item = State()
    admin_add_promo = State()
    admin_broadcast = State()

# ===== ТЕКСТЫ =====
TEXTS = {
    "ru": {
        "choose_lang": "Выбери язык / Choose language:",
        "consent": (
            "Используешь бота, приобретаешь услуги — значит согласен с публичной офертой:\n\n"
            f"✅ <a href='{URL_PRIVACY}'>Политика конфиденциальности</a>\n\n"
            f"❗️<a href='{URL_RULES}'>Правила использования</a>\n\n"
            "Ссылки 🔗 кликабельны."
        ),
        "accept": "✅ Принимаю",
        "subscribe_text": "Для использования бота подпишись на каналы:",
        "sub_btn": "🛒 Velso Shop",
        "check_sub": "✅ Проверить подписку",
        "not_sub": "Ты ещё не подписался. Подпишись и нажми «Проверить подписку».",
        "menu": "Меню",
        "services": "Услуги",
        "goods": "Товар",
        "offer": "Оферта",
        "profile": "Профиль",
        "support": "Поддержка",
        "referrals": "Рефералы",
        "back": "◀️ Назад",
        "cancel": "❌ Отмена",
        "pay": "💳 Оплатить",
        "topup": "💰 Пополнить",
        "enter_amount": "Введи сумму в USD для пополнения:",
        "choose_payment": "Выбери способ оплаты:",
        "pay_xrocket": "Оплатить через xRocket",
        "pay_cryptobot": "Оплатить через CryptoBot",
        "invoice_created": "Счёт создан! Перейди по ссылке для оплаты:\n{link}",
        "payment_error": "Ошибка создания счёта. Попробуй позже.",
        "profile_text": (
            "👤 <b>Профиль</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "💰 Баланс: <b>{balance} USD</b>\n"
            "🌐 Язык: {lang}\n"
            "🏆 Статус: {status}\n"
            "📅 Дата регистрации: {reg_date}\n"
            "👥 Рефералов: {ref_count}"
        ),
        "ref_text": (
            "🔗 <b>Реферальная система</b>\n\n"
            "Твоя ссылка:\n<code>{ref_link}</code>\n\n"
            "👥 Приглашено: {ref_count}\n"
            "💰 Заработано: {earned} USD (10% с пополнений рефералов)"
        ),
        "orders_history": "📋 Мои заказы",
        "no_orders": "У тебя пока нет заказов.",
        "services_list": "📦 <b>Услуги:</b>",
        "goods_list": "🛍 <b>Товар:</b>",
        "empty_list": "Пока пусто.",
        "buy_btn": "Купить за {price} USD",
        "insufficient": "Недостаточно средств. Пополни баланс.",
        "order_created": "Заказ создан! Ожидай выполнения.",
        "goods_delivered": "Товар выдан:\n{content}",
        "admin_panel": "⚙️ <b>Админ-панель</b>",
        "admin_add_service": "➕ Добавить услугу",
        "admin_add_goods": "➕ Добавить товар",
        "admin_orders": "📋 Заказы",
        "admin_stats": "📊 Статистика",
        "admin_broadcast": "📢 Рассылка",
        "admin_promo": "🎟 Промокоды",
        "admin_enter_name": "Введи название:",
        "admin_enter_desc": "Введи описание:",
        "admin_enter_price": "Введи цену в USD:",
        "admin_enter_content": "Введи контент (для товара):",
        "admin_item_added": "✅ Добавлено!",
        "admin_no_orders": "Заказов нет.",
        "admin_order_accept": "✅ Выполнено",
        "admin_order_reject": "❌ Не выполнено",
        "admin_reject_reason": "Введи причину отказа:",
        "admin_stats_text": "👥 Юзеров: {users}\n📦 Заказов: {orders}\n💰 Оборот: {turnover} USD",
        "admin_broadcast_text": "Введи текст рассылки:",
        "admin_broadcast_sent": "✅ Отправлено {count} юзерам.",
        "admin_promo_code": "Введи код:",
        "admin_promo_amount": "Введи сумму бонуса:",
        "admin_promo_uses": "Введи кол-во использований:",
        "admin_promo_added": "✅ Промокод добавлен!",
        "promo_enter": "Введи промокод:",
        "promo_success": "✅ Промокод активирован! +{amount} USD",
        "promo_invalid": "❌ Неверный или использованный промокод.",
        "order_done_notify": "✅ Твой заказ «{name}» выполнен!",
        "order_reject_notify": "❌ Заказ «{name}» отклонён. Причина: {reason}",
        "already": "Ты уже принял условия. Добро пожаловать! 🚀",
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
    kb.button(text=TEXTS["ru"]["accept"], callback_data="accept", style="success")
    return kb.as_markup()

def sub_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Velso Shop", url="https://t.me/VelsoShopInfo", style="primary")
    kb.button(text="✅ Проверить подписку", callback_data="check_sub", style="success")
    kb.adjust(1)
    return kb.as_markup()

def menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Услуги", callback_data="menu_services")
    kb.button(text="Товар", callback_data="menu_goods")
    kb.button(text="Оферта", url=URL_OFFER)
    kb.button(text="Профиль", callback_data="menu_profile")
    kb.button(text="Поддержка", url=f"https://t.me/{SUPPORT_USERNAME.replace('@','')}")
    kb.button(text="Рефералы", callback_data="menu_refs")
    kb.adjust(2, 2, 2)
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

def topup_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Оплатить", callback_data="pay_invoice", style="success")
    kb.button(text="❌ Отмена", callback_data="cancel_topup", style="danger")
    kb.adjust(1)
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
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Выполнено", callback_data=f"order_done:{order_id}", style="success")
    kb.button(text="❌ Не выполнено", callback_data=f"order_reject:{order_id}", style="danger")
    kb.adjust(2)
    return kb.as_markup()

# ===== ХЕЛПЕРЫ =====
async def check_sub(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

def get_main_menu_text(lang="ru"):
    return TEXTS[lang]["menu"]

# ===== ХЕНДЛЕРЫ =====

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    uid = message.from_user.id
    user = get_user(uid)
    
    if not user:
        # Парсим реферальный код
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
        # Уже принял, проверяем подписку
        if await check_sub(message.bot, uid):
            update_user(uid, subscribed=1)
            await message.answer(TEXTS[user[1]]["menu"], reply_markup=menu_kb())
        else:
            await message.answer(TEXTS[user[1]]["subscribe_text"], reply_markup=sub_kb())
        return
    
    # Новый юзер — выбор языка
    await message.answer(TEXTS["ru"]["choose_lang"], reply_markup=lang_kb())

@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    uid = callback.from_user.id
    update_user(uid, lang=lang)
    await callback.message.edit_text(
        TEXTS[lang]["consent"],
        reply_markup=accept_kb(),
        disable_web_page_preview=True
    )
    await callback.answer()

@dp.callback_query(F.data == "accept")
async def on_accept(callback: CallbackQuery):
    uid = callback.from_user.id
    update_user(uid, accepted=1)
    user = get_user(uid)
    lang = user[1] if user else "ru"
    
    # Удаляем сообщение с согласием и показываем подписку
    await callback.message.delete()
    await callback.message.answer(
        TEXTS[lang]["subscribe_text"],
        reply_markup=sub_kb()
    )
    await callback.answer()

@dp.callback_query(F.data == "check_sub")
async def on_check_sub(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    
    if await check_sub(callback.bot, uid):
        update_user(uid, subscribed=1)
        await callback.message.edit_text(TEXTS[lang]["menu"], reply_markup=menu_kb())
        await callback.answer("✅ Подписка подтверждена!")
    else:
        await callback.answer(TEXTS[lang]["not_sub"], show_alert=True)

@dp.callback_query(F.data == "back_to_menu")
async def on_back(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    await callback.message.edit_text(TEXTS[lang]["menu"], reply_markup=menu_kb())
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
        user_id=uid,
        balance=user[2],
        lang=user[1],
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
        await message.answer("Введи корректную сумму (число больше 0):")
        return
    
    await state.update_data(amount=amount)
    user = get_user(message.from_user.id)
    lang = user[1] if user else "ru"
    await message.answer(
        f"Сумма: {amount} USD\n\n{TEXTS[lang]['choose_payment']}",
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
                amount=amount,
                min_payment=0,
                num_payments=1,
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
                    currency_type=CurrencyType.FIAT,
                    fiat=FiatAsset.USD,
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
    await callback.message.edit_text(TEXTS[lang]["menu"], reply_markup=menu_kb())
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
    earned = ref_count * 0  # TODO: считать реально заработанное
    
    text = TEXTS[lang]["ref_text"].format(
        ref_link=ref_link,
        ref_count=ref_count,
        earned=earned
    )
    await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()

# ===== УСЛУГИ / ТОВАР =====
@dp.callback_query(F.data == "menu_services")
async def on_services(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM items WHERE type = 'service'")
    items = c.fetchall()
    conn.close()
    
    if not items:
        await callback.message.edit_text(TEXTS[lang]["empty_list"], reply_markup=back_kb())
    else:
        kb = InlineKeyboardBuilder()
        text = TEXTS[lang]["services_list"] + "\n\n"
        for item in items:
            text += f"• {item[1]} — {item[2]} USD\n"
            kb.button(text=f"Купить «{item[1]}»", callback_data=f"buy:service:{item[0]}")
        kb.button(text="◀️ Назад", callback_data="back_to_menu")
        kb.adjust(1)
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "menu_goods")
async def on_goods(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid)
    lang = user[1] if user else "ru"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM items WHERE type = 'goods'")
    items = c.fetchall()
    conn.close()
    
    if not items:
        await callback.message.edit_text(TEXTS[lang]["empty_list"], reply_markup=back_kb())
    else:
        kb = InlineKeyboardBuilder()
        text = TEXTS[lang]["goods_list"] + "\n\n"
        for item in items:
            text += f"• {item[1]} — {item[2]} USD\n"
            kb.button(text=f"Купить «{item[1]}»", callback_data=f"buy:goods:{item[0]}")
        kb.button(text="◀️ Назад", callback_data="back_to_menu")
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
    
    # Списываем баланс
    add_balance(uid, -price)
    
    if item_type == "goods":
        # Товар — выдается сразу
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO orders (user_id, item_type, item_name, price, status, created_at) VALUES (?, ?, ?, ?, 'completed', ?)",
                  (uid, item_type, name, price, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        await callback.message.edit_text(TEXTS[lang]["goods_delivered"].format(content=content), reply_markup=back_kb())
    else:
        # Услуга — заказ админу
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO orders (user_id, item_type, item_name, price, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                  (uid, item_type, name, price, datetime.now().isoformat()))
        order_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Уведомление админу
        try:
            await callback.bot.send_message(
                ADMIN_ID,
                f"🆕 Новый заказ #{order_id}\n\n"
                f"Юзер: {uid}\n"
                f"Услуга: {name}\n"
                f"Цена: {price} USD",
                reply_markup=admin_order_kb(order_id)
            )
        except:
            pass
        
        await callback.message.edit_text(TEXTS[lang]["order_created"], reply_markup=back_kb())
    
    await callback.answer()

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
    await state.update_data(item_type="service")
    await callback.message.edit_text(TEXTS["ru"]["admin_enter_name"])
    await callback.answer()

@dp.callback_query(F.data == "admin_add_goods")
async def admin_add_goods(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(States.admin_add_item)
    await state.update_data(item_type="goods")
    await callback.message.edit_text(TEXTS["ru"]["admin_enter_name"])
    await callback.answer()

@dp.message(States.admin_add_item)
async def admin_item_step(message: Message, state: FSMContext):
    data = await state.get_data()
    step = data.get("step", "name")
    
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
            await message.answer("Введи число:")
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
        # Отправляем каждый заказ с кнопками
        for o in orders:
            await callback.bot.send_message(
                ADMIN_ID,
                f"Заказ #{o[0]}\nЮзер: {o[1]}\nТовар: {o[2]}\nЦена: {o[3]} USD",
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
    await state.update_data(reject_order_id=order_id)
    await state.set_state(States.admin_add_item)  # используем это состояние для причины
    await state.update_data(step="reject_reason")
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
            await message.answer("Введи число:")
            return
        await state.update_data(amount=amount, step="uses")
        await message.answer(TEXTS["ru"]["admin_promo_uses"])
    elif step == "uses":
        try:
            uses = int(message.text)
        except:
            await message.answer("Введи целое число:")
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

# ===== ПРОМОКОД (ЮЗЕР) =====
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
            text += f"• {o[0]} — {o[1]} USD — {status_map.get(o[2], o[2])} ({o[3][:10]})\n"
        await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()

# ===== ОБРАБОТКА ПРИЧИНЫ ОТКАЗА =====
@dp.message(States.admin_add_item)
async def handle_reject_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("step") != "reject_reason":
        return
    
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
        # Возврат средств
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

# ===== ЗАПУСК =====
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())