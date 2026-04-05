import asyncio
import json
import os
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery
)
from aiogram.filters import Command
import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageChops

# ═══════════════════════════════════════
#           КОНФИГУРАЦИЯ
# ═══════════════════════════════════════
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = -1003885905357
CHANNEL_URL = "https://t.me/WellUtility"
ADMIN_ID = 8369509247
DB_FILE = "users.json"
CONFIG_FILE = "bot_config.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

awaiting_broadcast = set()
user_style = {}       # user_id -> selected QR style
admin_state = {}      # user_id -> {"action": ..., "key": ...}

# ═══════════════════════════════════════
#           СТИЛИ QR-КОДОВ
# ═══════════════════════════════════════

STYLES = {
    "dark_rounded": {"name": "🌑 Тёмный", "desc": "Тёмный фон, закруглённые модули"},
    "classic":      {"name": "⬜ Классический", "desc": "Чёрно-белый стандартный"},
    "dots":         {"name": "🔵 Точки", "desc": "Круглые модули"},
    "gradient_blue":{"name": "💎 Градиент", "desc": "Сине-фиолетовый градиент"},
    "neon_green":   {"name": "💚 Неон", "desc": "Неоновое свечение"},
    "sunset":       {"name": "🌅 Закат", "desc": "Оранжево-розовый градиент"},
    "ocean":        {"name": "🌊 Океан", "desc": "Бирюзовые точки на тёмном"},
    "minimal":      {"name": "✨ Минимал", "desc": "Тонкие модули с промежутками"},
}

# ═══════════════════════════════════════
#     ДОСТУПНЫЕ ЦВЕТА КНОПОК
#  Telegram Bot API 8.1+ — поле color
#  в InlineKeyboardButton
# ═══════════════════════════════════════

BUTTON_COLORS = {
    "default":  {"name": "⬜ По умолчанию", "value": None},
    "blue":     {"name": "🔵 Синий",        "value": "color_bot_button_blue"},
    "green":    {"name": "🟢 Зелёный",      "value": "color_bot_button_green"},
    "red":      {"name": "🔴 Красный",      "value": "color_bot_button_red"},
    "yellow":   {"name": "🟡 Жёлтый",       "value": "color_bot_button_yellow"},
    "purple":   {"name": "🟣 Фиолетовый",   "value": "color_bot_button_purple"},
    "white":    {"name": "⚪ Белый",         "value": "color_bot_button_white"},
}

# ═══════════════════════════════════════
#     КЛЮЧИ ЭМОДЗИ И ДЕФОЛТЫ
# ═══════════════════════════════════════

EMOJI_KEYS = {
    "welcome":   {"label": "👋 Приветствие",  "default": "👋"},
    "qr":        {"label": "🔲 QR-код",       "default": "🔲"},
    "success":   {"label": "✅ Успех",         "default": "✅"},
    "error":     {"label": "❌ Ошибка",        "default": "❌"},
    "lock":      {"label": "🔒 Блокировка",   "default": "🔒"},
    "wait":      {"label": "⏳ Ожидание",     "default": "⏳"},
    "style":     {"label": "🎨 Выбор стиля",  "default": "🎨"},
    "admin":     {"label": "👑 Админ",         "default": "👑"},
    "stats":     {"label": "📊 Статистика",    "default": "📊"},
    "broadcast": {"label": "📢 Рассылка",     "default": "📢"},
}


# ═══════════════════════════════════════
#     БАЗА ДАННЫХ / КОНФИГ
# ═══════════════════════════════════════

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_config():
    default = {"emoji": {}, "button_color": None}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for k, v in default.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    return default


def save_config(data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════
#     ХЕЛПЕРЫ — ЭМОДЗИ И КНОПКИ
# ═══════════════════════════════════════

def e(key: str) -> str:
    """Возвращает tg-emoji HTML или обычный fallback."""
    cfg = load_config()
    custom = cfg.get("emoji", {}).get(key)
    fallback = EMOJI_KEYS.get(key, {}).get("default", "")
    if custom and custom.get("id"):
        fb = custom.get("fallback", fallback)
        return f'<tg-emoji emoji-id="{custom["id"]}">{fb}</tg-emoji>'
    return fallback


def btn(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    """Создаёт кнопку с цветом из конфига (Bot API 8.1+)."""
    kwargs = {"text": text}
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url

    cfg = load_config()
    color = cfg.get("button_color")
    if color:
        kwargs["color"] = color

    try:
        return InlineKeyboardButton(**kwargs)
    except Exception:
        kwargs.pop("color", None)
        return InlineKeyboardButton(**kwargs)


# ═══════════════════════════════════════
#           ПРОВЕРКИ
# ═══════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        return False


# ═══════════════════════════════════════
#           КЛАВИАТУРЫ
# ═══════════════════════════════════════

def subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📢 Подписаться на канал", url=CHANNEL_URL)],
        [btn("✅ Проверить подписку", callback_data="check_sub")]
    ])


def main_keyboard(is_admin_user=False):
    buttons = [
        [btn("🔲 Создать QR-код", callback_data="generate_qr")],
        [btn("📢 Наш канал", url=CHANNEL_URL)],
    ]
    if is_admin_user:
        buttons.append([btn("👑 Админ-панель", callback_data="open_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def style_keyboard():
    buttons = []
    keys = list(STYLES.keys())
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i + j < len(keys):
                k = keys[i + j]
                row.append(btn(STYLES[k]["name"], callback_data=f"style_{k}"))
        buttons.append(row)
    buttons.append([btn("◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📊 Статистика", callback_data="admin_stats")],
        [btn("📢 Рассылка", callback_data="admin_broadcast")],
        [btn("🎨 Оформление", callback_data="admin_design")],
        [btn("🌐 Канал", url=CHANNEL_URL)],
        [btn("◀️ Назад", callback_data="back_main")]
    ])


def design_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("😀 Эмодзи", callback_data="design_emoji")],
        [btn("🎹 Цвет кнопок", callback_data="design_colors")],
        [btn("🔄 Сбросить всё", callback_data="design_reset")],
        [btn("◀️ Назад", callback_data="open_admin")]
    ])


def emoji_list_keyboard():
    cfg = load_config()
    custom = cfg.get("emoji", {})
    buttons = []
    keys = list(EMOJI_KEYS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i + j < len(keys):
                k = keys[i + j]
                label = EMOJI_KEYS[k]["label"]
                mark = " ✦" if k in custom and custom[k].get("id") else ""
                row.append(btn(f"{label}{mark}", callback_data=f"emj_set_{k}"))
        buttons.append(row)
    buttons.append([btn("🗑 Сбросить все эмодзи", callback_data="emj_reset_all")])
    buttons.append([btn("◀️ Назад", callback_data="admin_design")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def color_keyboard():
    cfg = load_config()
    current = cfg.get("button_color")
    buttons = []
    for key, info in BUTTON_COLORS.items():
        mark = " ✓" if info["value"] == current else ""
        buttons.append([btn(f"{info['name']}{mark}", callback_data=f"clr_{key}")])
    buttons.append([btn("◀️ Назад", callback_data="admin_design")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_keyboard(to_admin=False):
    target = "open_admin" if to_admin else "back_main"
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("◀️ Назад", callback_data=target)]
    ])


def cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("❌ Отмена", callback_data="cancel_broadcast")]
    ])


# ═══════════════════════════════════════
#           /start
# ═══════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    name = message.from_user.first_name or "пользователь"

    db = load_db()
    if str(user_id) not in db:
        db[str(user_id)] = {"username": message.from_user.username, "name": name, "qr_count": 0}
        save_db(db)

    if not is_admin(user_id) and not await is_subscribed(user_id):
        await message.answer(
            f"{e('welcome')} Привет, <b>{name}</b>!\n\n"
            f"{e('lock')} Для использования бота необходимо подписаться на наш канал.\n\n"
            f"После подписки нажми <b>«Проверить подписку»</b>",
            parse_mode="HTML",
            reply_markup=subscription_keyboard()
        )
        return

    await message.answer(
        f"{e('welcome')} Привет, <b>{name}</b>!\n\n"
        f"{e('qr')} Я умею генерировать <b>QR-коды</b> в разных стилях и дизайнах.\n\n"
        f"Нажми кнопку ниже, чтобы начать 👇",
        parse_mode="HTML",
        reply_markup=main_keyboard(is_admin_user=is_admin(user_id))
    )


# ═══════════════════════════════════════
#           CALLBACK — ПОЛЬЗОВАТЕЛЬ
# ═══════════════════════════════════════

@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        name = callback.from_user.first_name or "пользователь"
        await callback.message.edit_text(
            f"{e('success')} <b>Подписка подтверждена!</b>\n\n"
            f"{e('welcome')} Привет, <b>{name}</b>!\n\n"
            f"{e('qr')} Я умею генерировать <b>QR-коды</b> в разных стилях и дизайнах.\n\n"
            f"Нажми кнопку ниже, чтобы начать 👇",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
    else:
        await callback.answer("❌ Вы ещё не подписались на канал!", show_alert=True)


@dp.callback_query(F.data == "generate_qr")
async def choose_style(callback: CallbackQuery):
    style_list = "\n".join(f"  {s['name']} — {s['desc']}" for s in STYLES.values())
    await callback.message.edit_text(
        f"{e('style')} <b>Выберите стиль QR-кода:</b>\n\n{style_list}",
        parse_mode="HTML",
        reply_markup=style_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("style_"))
async def style_selected(callback: CallbackQuery):
    style_key = callback.data.replace("style_", "")
    if style_key not in STYLES:
        await callback.answer("❌ Неизвестный стиль", show_alert=True)
        return
    user_style[callback.from_user.id] = style_key
    await callback.message.edit_text(
        f"{e('qr')} <b>Генерация QR-кода</b>\n\n"
        f"Стиль: {STYLES[style_key]['name']}\n\n"
        f"Отправьте ссылку или текст, который хотите закодировать:",
        parse_mode="HTML",
        reply_markup=back_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    uid = callback.from_user.id
    user_style.pop(uid, None)
    admin_state.pop(uid, None)
    name = callback.from_user.first_name or "пользователь"
    await callback.message.edit_text(
        f"{e('welcome')} Привет, <b>{name}</b>!\n\n"
        f"{e('qr')} Я умею генерировать <b>QR-коды</b> в разных стилях и дизайнах.\n\n"
        f"Нажми кнопку ниже, чтобы начать 👇",
        parse_mode="HTML",
        reply_markup=main_keyboard(is_admin_user=is_admin(uid))
    )
    await callback.answer()


# ═══════════════════════════════════════
#           CALLBACK — АДМИН
# ═══════════════════════════════════════

@dp.callback_query(F.data == "open_admin")
async def open_admin_panel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    admin_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        f"{e('admin')} <b>Админ-панель</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    db = load_db()
    total = len(db)
    total_qr = sum(u.get("qr_count", 0) for u in db.values())
    cfg = load_config()
    custom_count = sum(1 for v in cfg.get("emoji", {}).values() if v.get("id"))
    color_name = "по умолчанию"
    for info in BUTTON_COLORS.values():
        if info["value"] == cfg.get("button_color"):
            color_name = info["name"]
            break

    await callback.message.edit_text(
        f"{e('stats')} <b>Статистика бота</b>\n\n"
        f"┌ 👥 Пользователей: <b>{total}</b>\n"
        f"├ 🔲 QR-кодов: <b>{total_qr}</b>\n"
        f"├ 😀 Кастомных эмодзи: <b>{custom_count}</b>\n"
        f"├ 🎹 Цвет кнопок: <b>{color_name}</b>\n"
        f"└ 🤖 Бот работает",
        parse_mode="HTML",
        reply_markup=back_keyboard(to_admin=True)
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    awaiting_broadcast.add(callback.from_user.id)
    admin_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        f"{e('broadcast')} <b>Рассылка</b>\n\n"
        "Отправьте сообщение для рассылки всем пользователям.\n\n"
        "Поддерживается: текст, фото, видео, документы.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery):
    awaiting_broadcast.discard(callback.from_user.id)
    await callback.message.edit_text(
        f"{e('admin')} <b>Админ-панель</b>\n\nРассылка отменена.",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )
    await callback.answer()


# ═══════════════════════════════════════
#     CALLBACK — ОФОРМЛЕНИЕ
# ═══════════════════════════════════════

@dp.callback_query(F.data == "admin_design")
async def design_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state.pop(callback.from_user.id, None)
    cfg = load_config()
    custom_count = sum(1 for v in cfg.get("emoji", {}).values() if v.get("id"))
    color_label = "по умолчанию"
    for info in BUTTON_COLORS.values():
        if info["value"] == cfg.get("button_color"):
            color_label = info["name"]
            break

    await callback.message.edit_text(
        f"{e('style')} <b>Оформление бота</b>\n\n"
        f"Кастомных эмодзи: <b>{custom_count} / {len(EMOJI_KEYS)}</b>\n"
        f"Цвет кнопок: <b>{color_label}</b>\n\n"
        f"Выберите что настроить:",
        parse_mode="HTML",
        reply_markup=design_keyboard()
    )
    await callback.answer()


# ── Эмодзи ──

@dp.callback_query(F.data == "design_emoji")
async def emoji_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "😀 <b>Настройка эмодзи</b>\n\n"
        "Выберите элемент для замены на премиум-эмодзи.\n"
        "Отмечены <b>✦</b> — уже настроенные.\n\n"
        "<i>После выбора отправьте сообщение с премиум-эмодзи</i>",
        parse_mode="HTML",
        reply_markup=emoji_list_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("emj_set_"))
async def emoji_set_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    key = callback.data.replace("emj_set_", "")
    if key not in EMOJI_KEYS:
        await callback.answer("❌ Неизвестный ключ", show_alert=True)
        return

    admin_state[callback.from_user.id] = {"action": "set_emoji", "key": key}
    label = EMOJI_KEYS[key]["label"]

    cfg = load_config()
    current = cfg.get("emoji", {}).get(key)
    if current and current.get("id"):
        current_text = f'premium emoji, id=<code>{current["id"]}</code>'
    else:
        current_text = "стандартный"

    await callback.message.edit_text(
        f"😀 <b>Настройка: {label}</b>\n\n"
        f"Текущий: {current_text}\n\n"
        f"Отправьте сообщение с <b>одним премиум-эмодзи</b>.\n\n"
        f"Или отправьте <code>reset</code> чтобы сбросить,\n"
        f"или <code>id:ЧИСЛО</code> чтобы задать ID вручную.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [btn("◀️ Назад", callback_data="design_emoji")]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "emj_reset_all")
async def emoji_reset_all(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cfg = load_config()
    cfg["emoji"] = {}
    save_config(cfg)
    await callback.message.edit_text(
        f"{e('success')} <b>Все кастомные эмодзи сброшены</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [btn("◀️ Назад", callback_data="design_emoji")]
        ])
    )
    await callback.answer()


# ── Цвета кнопок ──

@dp.callback_query(F.data == "design_colors")
async def color_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🎹 <b>Цвет кнопок</b>\n\n"
        "Выберите цвет для инлайн-кнопок бота.\n"
        "Отмечен <b>✓</b> — текущий.\n\n"
        "<i>Требуется Telegram Bot API 8.1+\n"
        "и aiogram с поддержкой поля color</i>",
        parse_mode="HTML",
        reply_markup=color_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("clr_"))
async def color_selected(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    color_key = callback.data.replace("clr_", "")
    if color_key not in BUTTON_COLORS:
        return

    cfg = load_config()
    cfg["button_color"] = BUTTON_COLORS[color_key]["value"]
    save_config(cfg)

    await callback.message.edit_text(
        f"🎹 <b>Цвет кнопок обновлён</b>\n\n"
        f"Новый цвет: <b>{BUTTON_COLORS[color_key]['name']}</b>\n\n"
        f"Применится к новым сообщениям.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [btn("🎹 Назад к цветам", callback_data="design_colors")],
            [btn("◀️ Оформление", callback_data="admin_design")]
        ])
    )
    await callback.answer()


# ── Сброс всего ──

@dp.callback_query(F.data == "design_reset")
async def design_reset(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cfg = load_config()
    cfg["emoji"] = {}
    cfg["button_color"] = None
    save_config(cfg)
    await callback.message.edit_text(
        f"{e('success')} <b>Оформление сброшено</b>\n\n"
        "Все настройки возвращены к стандартным.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [btn("◀️ Назад", callback_data="admin_design")]
        ])
    )
    await callback.answer()


# ═══════════════════════════════════════
#           ОБРАБОТКА ТЕКСТА
# ═══════════════════════════════════════

def extract_custom_emoji_id(message: Message) -> str | None:
    """Извлекает custom_emoji_id из entities сообщения."""
    if not message.entities:
        return None
    for ent in message.entities:
        if ent.type == "custom_emoji":
            return ent.custom_emoji_id
    return None


@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # ── Админ: настройка эмодзи ──
    state = admin_state.get(user_id)
    if is_admin(user_id) and state and state.get("action") == "set_emoji":
        key = state["key"]
        admin_state.pop(user_id, None)

        # Сброс
        if text.lower() == "reset":
            cfg = load_config()
            cfg.get("emoji", {}).pop(key, None)
            save_config(cfg)
            await message.answer(
                f"{e('success')} Эмодзи <b>{EMOJI_KEYS[key]['label']}</b> сброшен.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [btn("◀️ Назад", callback_data="design_emoji")]
                ])
            )
            return

        # Ручной ввод ID: "id:5870982283724328568"
        emoji_id = None
        id_match = re.match(r'^id[:\s]?(\d{5,})$', text)
        if id_match:
            emoji_id = id_match.group(1)

        # Из entities (когда отправлен реальный премиум-эмодзи)
        if not emoji_id:
            emoji_id = extract_custom_emoji_id(message)

        # Просто число
        if not emoji_id and text.isdigit() and len(text) > 5:
            emoji_id = text

        if not emoji_id:
            await message.answer(
                f"{e('error')} <b>Не найден премиум-эмодзи</b>\n\n"
                "Отправьте сообщение с <b>премиум-эмодзи</b>,\n"
                "или <code>id:ЧИСЛО</code> для ввода ID вручную.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [btn("🔄 Попробовать снова", callback_data=f"emj_set_{key}")],
                    [btn("◀️ Назад", callback_data="design_emoji")]
                ])
            )
            return

        # Определяем fallback
        fallback = EMOJI_KEYS[key]["default"]
        if message.text:
            for ch in message.text:
                if ord(ch) > 127 and not ch.isdigit():
                    fallback = ch
                    break

        cfg = load_config()
        cfg.setdefault("emoji", {})[key] = {"id": str(emoji_id), "fallback": fallback}
        save_config(cfg)

        await message.answer(
            f"{e('success')} <b>Эмодзи обновлён!</b>\n\n"
            f"Элемент: <b>{EMOJI_KEYS[key]['label']}</b>\n"
            f"ID: <code>{emoji_id}</code>\n\n"
            f"Превью: {e(key)}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [btn("😀 Ещё эмодзи", callback_data="design_emoji")],
                [btn("◀️ Оформление", callback_data="admin_design")]
            ])
        )
        return

    # ── Рассылка от админа ──
    if is_admin(user_id) and user_id in awaiting_broadcast:
        awaiting_broadcast.discard(user_id)
        db = load_db()
        success, failed = 0, 0
        for uid in db:
            try:
                await bot.copy_message(int(uid), user_id, message.message_id)
                success += 1
            except Exception:
                failed += 1
        await message.answer(
            f"{e('broadcast')} <b>Рассылка завершена</b>\n\n"
            f"┌ ✅ Доставлено: <b>{success}</b>\n"
            f"└ ❌ Ошибок: <b>{failed}</b>",
            parse_mode="HTML",
            reply_markup=main_keyboard(is_admin_user=True)
        )
        return

    # ── Проверка подписки ──
    if not is_admin(user_id) and not await is_subscribed(user_id):
        await message.answer(
            f"{e('lock')} <b>Доступ ограничен</b>\n\n"
            "Подпишитесь на канал для использования бота.",
            parse_mode="HTML",
            reply_markup=subscription_keyboard()
        )
        return

    # ── Генерация QR ──
    if not text:
        return

    style = user_style.pop(user_id, "dark_rounded")
    wait_msg = await message.answer(f"{e('wait')} <b>Генерирую QR-код...</b>", parse_mode="HTML")

    try:
        qr_file = generate_qr(text, user_id, style)
        photo = FSInputFile(qr_file)

        db = load_db()
        if str(user_id) not in db:
            db[str(user_id)] = {"qr_count": 0}
        db[str(user_id)]["qr_count"] = db[str(user_id)].get("qr_count", 0) + 1
        save_db(db)

        style_name = STYLES.get(style, {}).get("name", "")
        await message.answer_photo(
            photo=photo,
            caption=f"{e('success')} <b>QR-код готов!</b>\n"
                    f"Стиль: {style_name}\n\n"
                    "Нажми кнопку ниже чтобы создать ещё 👇",
            parse_mode="HTML",
            reply_markup=main_keyboard(is_admin_user=is_admin(user_id))
        )
        os.remove(qr_file)
    except Exception:
        await message.answer(
            f"{e('error')} <b>Ошибка при создании QR-кода</b>\n\nПопробуйте ещё раз.",
            parse_mode="HTML",
            reply_markup=main_keyboard(is_admin_user=is_admin(user_id))
        )
    finally:
        await wait_msg.delete()


# ═══════════════════════════════════════
#           QR ГЕНЕРАТОРЫ
# ═══════════════════════════════════════

def generate_qr(text, user_id, style="dark_rounded"):
    generators = {
        "dark_rounded": gen_dark_rounded, "classic": gen_classic,
        "dots": gen_dots, "gradient_blue": gen_gradient,
        "neon_green": gen_neon, "sunset": gen_sunset,
        "ocean": gen_ocean, "minimal": gen_minimal,
    }
    return generators.get(style, gen_dark_rounded)(text, user_id)


def _make_matrix(text):
    qr = qrcode.QRCode(version=1, box_size=50, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    return qr.get_matrix()


def _has_neighbor(matrix, size, row, col, dr, dc):
    nr, nc = row + dr, col + dc
    return matrix[nr][nc] if 0 <= nr < size and 0 <= nc < size else False


def _draw_rounded(draw, matrix, size, border, ms, radius, bg, color_fn):
    for row in range(size):
        for col in range(size):
            if not matrix[row][col]:
                continue
            x, y = (col + border) * ms, (row + border) * ms
            c = color_fn(row, col, size)
            t = _has_neighbor(matrix, size, row, col, -1, 0)
            r = _has_neighbor(matrix, size, row, col, 0, 1)
            b = _has_neighbor(matrix, size, row, col, 1, 0)
            l = _has_neighbor(matrix, size, row, col, 0, -1)
            draw.rectangle([(x, y), (x + ms, y + ms)], fill=c)
            if not t and not l:
                draw.rectangle([(x, y), (x + radius, y + radius)], fill=bg)
                draw.ellipse([(x, y), (x + radius * 2, y + radius * 2)], fill=c)
            if not t and not r:
                draw.rectangle([(x + ms - radius, y), (x + ms, y + radius)], fill=bg)
                draw.ellipse([(x + ms - radius * 2, y), (x + ms, y + radius * 2)], fill=c)
            if not b and not r:
                draw.rectangle([(x + ms - radius, y + ms - radius), (x + ms, y + ms)], fill=bg)
                draw.ellipse([(x + ms - radius * 2, y + ms - radius * 2), (x + ms, y + ms)], fill=c)
            if not b and not l:
                draw.rectangle([(x, y + ms - radius), (x + radius, y + ms)], fill=bg)
                draw.ellipse([(x, y + ms - radius * 2), (x + radius * 2, y + ms)], fill=c)


def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def gen_dark_rounded(text, uid):
    m = _make_matrix(text); ms, brd, sz = 50, 2, len(m)
    img = Image.new('RGB', ((sz + brd * 2) * ms,) * 2, (12, 12, 12))
    _draw_rounded(ImageDraw.Draw(img), m, sz, brd, ms, 22, (12, 12, 12), lambda r, c, s: (255, 255, 255))
    f = f"qr_{uid}.png"; img.save(f); return f


def gen_classic(text, uid):
    m = _make_matrix(text); ms, brd, sz = 50, 2, len(m)
    img = Image.new('RGB', ((sz + brd * 2) * ms,) * 2, (255, 255, 255))
    d = ImageDraw.Draw(img)
    for row in range(sz):
        for col in range(sz):
            if m[row][col]:
                x, y = (col + brd) * ms, (row + brd) * ms
                d.rectangle([(x, y), (x + ms, y + ms)], fill=(0, 0, 0))
    f = f"qr_{uid}.png"; img.save(f); return f


def gen_dots(text, uid):
    m = _make_matrix(text); ms, brd, sz = 50, 2, len(m)
    img = Image.new('RGB', ((sz + brd * 2) * ms,) * 2, (245, 245, 250))
    d = ImageDraw.Draw(img); r = ms // 2 - 3
    for row in range(sz):
        for col in range(sz):
            if m[row][col]:
                cx, cy = (col + brd) * ms + ms // 2, (row + brd) * ms + ms // 2
                d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(30, 60, 180))
    f = f"qr_{uid}.png"; img.save(f); return f


def gen_gradient(text, uid):
    m = _make_matrix(text); ms, brd, sz = 50, 2, len(m)
    bg = (255, 255, 255)
    img = Image.new('RGB', ((sz + brd * 2) * ms,) * 2, bg)
    _draw_rounded(ImageDraw.Draw(img), m, sz, brd, ms, 20, bg,
                  lambda r, c, s: _lerp((50, 50, 220), (180, 50, 220), (r + c) / (2 * s) if s else 0))
    f = f"qr_{uid}.png"; img.save(f); return f


def gen_neon(text, uid):
    m = _make_matrix(text); ms, brd, sz = 50, 4, len(m)
    isz = (sz + brd * 2) * ms; bg = (10, 10, 15)
    glow = Image.new('RGB', (isz, isz), bg); gd = ImageDraw.Draw(glow)
    for row in range(sz):
        for col in range(sz):
            if m[row][col]:
                x, y = (col + brd) * ms, (row + brd) * ms
                gd.rectangle([(x - 8, y - 8), (x + ms + 8, y + ms + 8)], fill=(0, 255, 100))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img = Image.new('RGB', (isz, isz), bg); d = ImageDraw.Draw(img)
    for row in range(sz):
        for col in range(sz):
            if m[row][col]:
                x, y = (col + brd) * ms, (row + brd) * ms
                d.rectangle([(x, y), (x + ms, y + ms)], fill=(180, 255, 200))
    img = ImageChops.lighter(glow, img)
    f = f"qr_{uid}.png"; img.save(f); return f


def gen_sunset(text, uid):
    m = _make_matrix(text); ms, brd, sz = 50, 2, len(m)
    bg = (255, 250, 245)
    img = Image.new('RGB', ((sz + brd * 2) * ms,) * 2, bg)
    _draw_rounded(ImageDraw.Draw(img), m, sz, brd, ms, 18, bg,
                  lambda r, c, s: _lerp((255, 100, 50), (200, 50, 120), r / s if s else 0))
    f = f"qr_{uid}.png"; img.save(f); return f


def gen_ocean(text, uid):
    m = _make_matrix(text); ms, brd, sz = 50, 3, len(m)
    img = Image.new('RGB', ((sz + brd * 2) * ms,) * 2, (15, 20, 35))
    d = ImageDraw.Draw(img); r = ms // 2 - 2
    for row in range(sz):
        for col in range(sz):
            if m[row][col]:
                cx, cy = (col + brd) * ms + ms // 2, (row + brd) * ms + ms // 2
                t = (row + col) / (2 * sz) if sz else 0
                d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=_lerp((0, 200, 200), (0, 100, 220), t))
    f = f"qr_{uid}.png"; img.save(f); return f


def gen_minimal(text, uid):
    m = _make_matrix(text); ms, brd, sz = 50, 3, len(m)
    img = Image.new('RGB', ((sz + brd * 2) * ms,) * 2, (252, 252, 252))
    d = ImageDraw.Draw(img); gap = 6
    for row in range(sz):
        for col in range(sz):
            if m[row][col]:
                x, y = (col + brd) * ms + gap, (row + brd) * ms + gap
                w = ms - gap * 2
                d.rounded_rectangle([(x, y), (x + w, y + w)], radius=10, fill=(40, 40, 40))
    f = f"qr_{uid}.png"; img.save(f); return f


# ═══════════════════════════════════════
#           ЗАПУСК
# ═══════════════════════════════════════

async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
