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
user_style = {}
admin_state = {}

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

BUTTON_COLORS = {
    "default":  {"name": "⬜ По умолчанию", "value": None},
    "blue":     {"name": "🔵 Синий",        "value": "color_bot_button_blue"},
    "green":    {"name": "🟢 Зелёный",      "value": "color_bot_button_green"},
    "red":      {"name": "🔴 Красный",      "value": "color_bot_button_red"},
    "yellow":   {"name": "🟡 Жёлтый",       "value": "color_bot_button_yellow"},
    "purple":   {"name": "🟣 Фиолетовый",   "value": "color_bot_button_purple"},
    "white":    {"name": "⚪ Белый",         "value": "color_bot_button_white"},
}

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
#  ДЕФОЛТНЫЕ ТЕКСТЫ СООБЩЕНИЙ И КНОПОК
#
#  Плейсхолдеры в сообщениях:
#    {e_welcome}, {e_qr}, {e_success}... — эмодзи
#    {name}   — имя пользователя
#    {style}  — название стиля QR
#    {success}, {failed} — счётчики рассылки
#    {styles_list} — список стилей
# ═══════════════════════════════════════

DEFAULT_MSGS = {
    "msg_welcome": (
        "{e_welcome} Привет, <b>{name}</b>!\n\n"
        "{e_qr} Я умею генерировать <b>QR-коды</b> в разных стилях и дизайнах.\n\n"
        "Нажми кнопку ниже, чтобы начать 👇"
    ),
    "msg_need_sub": (
        "{e_welcome} Привет, <b>{name}</b>!\n\n"
        "{e_lock} Для использования бота необходимо подписаться на наш канал.\n\n"
        "После подписки нажми <b>«Проверить подписку»</b>"
    ),
    "msg_sub_ok": (
        "{e_success} <b>Подписка подтверждена!</b>\n\n"
        "{e_welcome} Привет, <b>{name}</b>!\n\n"
        "{e_qr} Я умею генерировать <b>QR-коды</b> в разных стилях и дизайнах.\n\n"
        "Нажми кнопку ниже, чтобы начать 👇"
    ),
    "msg_choose_style": (
        "{e_style} <b>Выберите стиль QR-кода:</b>\n\n{styles_list}"
    ),
    "msg_enter_text": (
        "{e_qr} <b>Генерация QR-кода</b>\n\n"
        "Стиль: {style}\n\n"
        "Отправьте ссылку или текст, который хотите закодировать:"
    ),
    "msg_generating": "{e_wait} <b>Генерирую QR-код...</b>",
    "msg_qr_ready": (
        "{e_success} <b>QR-код готов!</b>\n"
        "Стиль: {style}\n\n"
        "Нажми кнопку ниже чтобы создать ещё 👇"
    ),
    "msg_qr_error": "{e_error} <b>Ошибка при создании QR-кода</b>\n\nПопробуйте ещё раз.",
    "msg_access_denied": (
        "{e_lock} <b>Доступ ограничен</b>\n\n"
        "Подпишитесь на канал для использования бота."
    ),
    "msg_broadcast_ask": (
        "{e_broadcast} <b>Рассылка</b>\n\n"
        "Отправьте сообщение для рассылки всем пользователям.\n\n"
        "Поддерживается: текст, фото, видео, документы."
    ),
    "msg_broadcast_done": (
        "{e_broadcast} <b>Рассылка завершена</b>\n\n"
        "┌ ✅ Доставлено: <b>{success}</b>\n"
        "└ ❌ Ошибок: <b>{failed}</b>"
    ),
    "msg_admin_panel": "{e_admin} <b>Админ-панель</b>\n\nВыбери действие:",
    "msg_stats": (
        "{e_stats} <b>Статистика бота</b>\n\n"
        "┌ 👥 Пользователей: <b>{total_users}</b>\n"
        "├ 🔲 QR-кодов: <b>{total_qr}</b>\n"
        "└ 🤖 Бот работает"
    ),
}

MSG_META = {
    "msg_welcome":       "👋 Приветствие",
    "msg_need_sub":      "🔒 Требуется подписка",
    "msg_sub_ok":        "✅ Подписка ОК",
    "msg_choose_style":  "🎨 Выбор стиля",
    "msg_enter_text":    "📝 Ввод текста",
    "msg_generating":    "⏳ Генерация",
    "msg_qr_ready":      "✅ QR готов",
    "msg_qr_error":      "❌ Ошибка QR",
    "msg_access_denied": "🔒 Нет доступа",
    "msg_broadcast_ask": "📢 Рассылка текст",
    "msg_broadcast_done":"📢 Рассылка готово",
    "msg_admin_panel":   "👑 Админ-панель",
    "msg_stats":         "📊 Статистика",
}

DEFAULT_BTNS = {
    "btn_create_qr":  "🔲 Создать QR-код",
    "btn_subscribe":   "📢 Подписаться на канал",
    "btn_check_sub":   "✅ Проверить подписку",
    "btn_channel":     "📢 Наш канал",
    "btn_admin":       "👑 Админ-панель",
    "btn_back":        "◀️ Назад",
    "btn_cancel":      "❌ Отмена",
    "btn_stats":       "📊 Статистика",
    "btn_broadcast":   "📢 Рассылка",
    "btn_design":      "🎨 Оформление",
    "btn_web_channel": "🌐 Канал",
}

BTN_META = {
    "btn_create_qr":  "🔲 Создать QR",
    "btn_subscribe":   "📢 Подписаться",
    "btn_check_sub":   "✅ Проверить подписку",
    "btn_channel":     "📢 Наш канал",
    "btn_admin":       "👑 Админ-панель",
    "btn_back":        "◀️ Назад",
    "btn_cancel":      "❌ Отмена",
    "btn_stats":       "📊 Статистика",
    "btn_broadcast":   "📢 Рассылка",
    "btn_design":      "🎨 Оформление",
    "btn_web_channel": "🌐 Канал",
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
    default = {"emoji": {}, "button_color": None, "texts": {}, "buttons": {}, "style_names": {}}
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
#  ХЕЛПЕРЫ — ЭМОДЗИ / ТЕКСТЫ / КНОПКИ
# ═══════════════════════════════════════

def e(key: str) -> str:
    """Премиум tg-emoji или обычный fallback."""
    cfg = load_config()
    custom = cfg.get("emoji", {}).get(key)
    fallback = EMOJI_KEYS.get(key, {}).get("default", "")
    if custom and custom.get("id"):
        fb = custom.get("fallback", fallback)
        return f'<tg-emoji emoji-id="{custom["id"]}">{fb}</tg-emoji>'
    return fallback


def t(key: str, **kwargs) -> str:
    """Получает текст сообщения (кастомный или дефолтный), подставляет плейсхолдеры."""
    cfg = load_config()
    raw = cfg.get("texts", {}).get(key) or DEFAULT_MSGS.get(key, key)
    # Подставляем эмодзи {e_xxx}
    for ek in EMOJI_KEYS:
        raw = raw.replace(f"{{e_{ek}}}", e(ek))
    # Подставляем аргументы {name}, {style}, ...
    for k, v in kwargs.items():
        raw = raw.replace(f"{{{k}}}", str(v))
    return raw


def b(key: str) -> str:
    """Получает текст кнопки (кастомный или дефолтный)."""
    cfg = load_config()
    return cfg.get("buttons", {}).get(key) or DEFAULT_BTNS.get(key, key)


def sname(key: str) -> str:
    """Получает название кнопки стиля QR (кастомное или дефолтное)."""
    cfg = load_config()
    return cfg.get("style_names", {}).get(key) or STYLES.get(key, {}).get("name", key)


def mkbtn(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    """Создаёт InlineKeyboardButton с цветом из конфига."""
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

def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

async def is_subscribed(uid: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL_ID, uid)
        return m.status not in ("left", "kicked", "banned")
    except Exception:
        return False


# ═══════════════════════════════════════
#           КЛАВИАТУРЫ
# ═══════════════════════════════════════

def kb_sub():
    return InlineKeyboardMarkup(inline_keyboard=[
        [mkbtn(b("btn_subscribe"), url=CHANNEL_URL)],
        [mkbtn(b("btn_check_sub"), callback_data="check_sub")]
    ])

def kb_main(admin=False):
    rows = [
        [mkbtn(b("btn_create_qr"), callback_data="generate_qr")],
        [mkbtn(b("btn_channel"), url=CHANNEL_URL)],
    ]
    if admin:
        rows.append([mkbtn(b("btn_admin"), callback_data="open_admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_styles():
    rows = []
    keys = list(STYLES.keys())
    for i in range(0, len(keys), 2):
        row = [mkbtn(sname(keys[i+j]), callback_data=f"style_{keys[i+j]}")
               for j in range(2) if i+j < len(keys)]
        rows.append(row)
    rows.append([mkbtn(b("btn_back"), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [mkbtn(b("btn_stats"), callback_data="admin_stats")],
        [mkbtn(b("btn_broadcast"), callback_data="admin_broadcast")],
        [mkbtn(b("btn_design"), callback_data="admin_design")],
        [mkbtn(b("btn_web_channel"), url=CHANNEL_URL)],
        [mkbtn(b("btn_back"), callback_data="back_main")]
    ])

def kb_design():
    return InlineKeyboardMarkup(inline_keyboard=[
        [mkbtn("😀 Эмодзи", callback_data="design_emoji")],
        [mkbtn("📝 Тексты", callback_data="design_texts")],
        [mkbtn("🔘 Кнопки", callback_data="design_buttons")],
        [mkbtn("🎨 Кнопки стилей", callback_data="design_style_btns")],
        [mkbtn("🎹 Цвет кнопок", callback_data="design_colors")],
        [mkbtn("🔄 Сбросить всё", callback_data="design_reset")],
        [mkbtn(b("btn_back"), callback_data="open_admin")]
    ])

def kb_back(target="back_main"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [mkbtn(b("btn_back"), callback_data=target)]
    ])

def kb_cancel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [mkbtn(b("btn_cancel"), callback_data="cancel_broadcast")]
    ])


# ── Клавиатуры для редактирования текстов ──

def kb_msg_list():
    """Список сообщений для редактирования."""
    cfg = load_config()
    custom_texts = cfg.get("texts", {})
    rows = []
    keys = list(MSG_META.keys())
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i + j < len(keys):
                k = keys[i + j]
                label = MSG_META[k]
                mark = " ✦" if k in custom_texts else ""
                row.append(mkbtn(f"{label}{mark}", callback_data=f"txe_{k}"))
        rows.append(row)
    rows.append([mkbtn("🗑 Сбросить все тексты", callback_data="txt_reset_msgs")])
    rows.append([mkbtn(b("btn_back"), callback_data="admin_design")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_btn_list():
    """Список кнопок для редактирования."""
    cfg = load_config()
    custom_btns = cfg.get("buttons", {})
    rows = []
    keys = list(BTN_META.keys())
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i + j < len(keys):
                k = keys[i + j]
                label = BTN_META[k]
                mark = " ✦" if k in custom_btns else ""
                row.append(mkbtn(f"{label}{mark}", callback_data=f"bte_{k}"))
        rows.append(row)
    rows.append([mkbtn("🗑 Сбросить все кнопки", callback_data="txt_reset_btns")])
    rows.append([mkbtn(b("btn_back"), callback_data="admin_design")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_style_btn_list():
    """Список кнопок стилей QR для редактирования."""
    cfg = load_config()
    custom = cfg.get("style_names", {})
    rows = []
    keys = list(STYLES.keys())
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i + j < len(keys):
                k = keys[i + j]
                label = STYLES[k]["name"]
                mark = " ✦" if k in custom else ""
                row.append(mkbtn(f"{label}{mark}", callback_data=f"stb_{k}"))
        rows.append(row)
    rows.append([mkbtn("🗑 Сбросить все стили", callback_data="stb_reset")])
    rows.append([mkbtn(b("btn_back"), callback_data="admin_design")])
    return InlineKeyboardMarkup(inline_keyboard=rows)



    cfg = load_config()
    custom = cfg.get("emoji", {})
    rows = []
    keys = list(EMOJI_KEYS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i + j < len(keys):
                k = keys[i + j]
                label = EMOJI_KEYS[k]["label"]
                mark = " ✦" if k in custom and custom[k].get("id") else ""
                row.append(mkbtn(f"{label}{mark}", callback_data=f"emj_set_{k}"))
        rows.append(row)
    rows.append([mkbtn("🗑 Сбросить все эмодзи", callback_data="emj_reset_all")])
    rows.append([mkbtn(b("btn_back"), callback_data="admin_design")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_colors():
    cfg = load_config()
    current = cfg.get("button_color")
    rows = []
    for key, info in BUTTON_COLORS.items():
        mark = " ✓" if info["value"] == current else ""
        rows.append([mkbtn(f"{info['name']}{mark}", callback_data=f"clr_{key}")])
    rows.append([mkbtn(b("btn_back"), callback_data="admin_design")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══════════════════════════════════════
#           /start
# ═══════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    name = message.from_user.first_name or "пользователь"

    db = load_db()
    if str(uid) not in db:
        db[str(uid)] = {"username": message.from_user.username, "name": name, "qr_count": 0}
        save_db(db)

    if not is_admin(uid) and not await is_subscribed(uid):
        await message.answer(t("msg_need_sub", name=name), parse_mode="HTML", reply_markup=kb_sub())
        return

    await message.answer(t("msg_welcome", name=name), parse_mode="HTML", reply_markup=kb_main(admin=is_admin(uid)))


# ═══════════════════════════════════════
#     CALLBACK — ПОЛЬЗОВАТЕЛЬ
# ═══════════════════════════════════════

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        name = callback.from_user.first_name or "пользователь"
        await callback.message.edit_text(
            t("msg_sub_ok", name=name), parse_mode="HTML", reply_markup=kb_main())
    else:
        await callback.answer("❌ Вы ещё не подписались на канал!", show_alert=True)


@dp.callback_query(F.data == "generate_qr")
async def cb_choose_style(callback: CallbackQuery):
    sl = "\n".join(f"  {s['name']} — {s['desc']}" for s in STYLES.values())
    await callback.message.edit_text(
        t("msg_choose_style", styles_list=sl), parse_mode="HTML", reply_markup=kb_styles())
    await callback.answer()


@dp.callback_query(F.data.startswith("style_"))
async def cb_style(callback: CallbackQuery):
    sk = callback.data[6:]
    if sk not in STYLES:
        await callback.answer("❌ Неизвестный стиль", show_alert=True); return
    user_style[callback.from_user.id] = sk
    await callback.message.edit_text(
        t("msg_enter_text", style=STYLES[sk]["name"]), parse_mode="HTML", reply_markup=kb_back())
    await callback.answer()


@dp.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery):
    uid = callback.from_user.id
    user_style.pop(uid, None); admin_state.pop(uid, None)
    name = callback.from_user.first_name or "пользователь"
    await callback.message.edit_text(
        t("msg_welcome", name=name), parse_mode="HTML", reply_markup=kb_main(admin=is_admin(uid)))
    await callback.answer()


# ═══════════════════════════════════════
#     CALLBACK — АДМИН (основные)
# ═══════════════════════════════════════

@dp.callback_query(F.data == "open_admin")
async def cb_admin(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True); return
    admin_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        t("msg_admin_panel"), parse_mode="HTML", reply_markup=kb_admin())
    await callback.answer()


@dp.callback_query(F.data == "admin_stats")
async def cb_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    db = load_db()
    await callback.message.edit_text(
        t("msg_stats",
          total_users=len(db),
          total_qr=sum(u.get("qr_count", 0) for u in db.values())),
        parse_mode="HTML", reply_markup=kb_back("open_admin"))
    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def cb_broadcast(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    awaiting_broadcast.add(callback.from_user.id)
    admin_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        t("msg_broadcast_ask"), parse_mode="HTML", reply_markup=kb_cancel())
    await callback.answer()


@dp.callback_query(F.data == "cancel_broadcast")
async def cb_cancel_bcast(callback: CallbackQuery):
    awaiting_broadcast.discard(callback.from_user.id)
    await callback.message.edit_text(
        t("msg_admin_panel") + "\n\nРассылка отменена.",
        parse_mode="HTML", reply_markup=kb_admin())
    await callback.answer()


# ═══════════════════════════════════════
#     CALLBACK — ОФОРМЛЕНИЕ (главная)
# ═══════════════════════════════════════

@dp.callback_query(F.data == "admin_design")
async def cb_design(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    admin_state.pop(callback.from_user.id, None)
    cfg = load_config()
    ce = sum(1 for v in cfg.get("emoji", {}).values() if v.get("id"))
    ct = len(cfg.get("texts", {}))
    cb_ = len(cfg.get("buttons", {}))
    cs = len(cfg.get("style_names", {}))
    cl = "по умолчанию"
    for info in BUTTON_COLORS.values():
        if info["value"] == cfg.get("button_color"):
            cl = info["name"]; break
    await callback.message.edit_text(
        f"{e('style')} <b>Оформление бота</b>\n\n"
        f"Эмодзи: <b>{ce} / {len(EMOJI_KEYS)}</b>\n"
        f"Тексты: <b>{ct} / {len(DEFAULT_MSGS)}</b>\n"
        f"Кнопки: <b>{cb_} / {len(DEFAULT_BTNS)}</b>\n"
        f"Стили QR: <b>{cs} / {len(STYLES)}</b>\n"
        f"Цвет: <b>{cl}</b>",
        parse_mode="HTML", reply_markup=kb_design())
    await callback.answer()


# ═══════════════════════════════════════
#     CALLBACK — ЭМОДЗИ
# ═══════════════════════════════════════

@dp.callback_query(F.data == "design_emoji")
async def cb_emoji_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    admin_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "😀 <b>Настройка эмодзи</b>\n\n"
        "Выберите элемент для замены на премиум-эмодзи.\n"
        "<b>✦</b> — уже настроенные.\n\n"
        "<i>После выбора отправьте премиум-эмодзи или <code>id:ЧИСЛО</code></i>",
        parse_mode="HTML", reply_markup=kb_emoji_list())
    await callback.answer()


@dp.callback_query(F.data.startswith("emj_set_"))
async def cb_emoji_set(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    key = callback.data[8:]
    if key not in EMOJI_KEYS:
        await callback.answer("❌", show_alert=True); return
    admin_state[callback.from_user.id] = {"action": "set_emoji", "key": key}
    cfg = load_config()
    cur = cfg.get("emoji", {}).get(key)
    ct = f'id=<code>{cur["id"]}</code>' if cur and cur.get("id") else "стандартный"
    await callback.message.edit_text(
        f"😀 <b>{EMOJI_KEYS[key]['label']}</b>\n\n"
        f"Текущий: {ct}\n\n"
        f"Отправьте <b>премиум-эмодзи</b>, <code>id:ЧИСЛО</code> или <code>reset</code>",
        parse_mode="HTML", reply_markup=kb_back("design_emoji"))
    await callback.answer()


@dp.callback_query(F.data == "emj_reset_all")
async def cb_emoji_reset(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cfg = load_config(); cfg["emoji"] = {}; save_config(cfg)
    await callback.message.edit_text(
        "✅ <b>Все эмодзи сброшены</b>",
        parse_mode="HTML", reply_markup=kb_back("design_emoji"))
    await callback.answer()


# ═══════════════════════════════════════
#     CALLBACK — ТЕКСТЫ СООБЩЕНИЙ
# ═══════════════════════════════════════

@dp.callback_query(F.data == "design_texts")
async def cb_texts_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    admin_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "📝 <b>Тексты сообщений</b>\n\n"
        "Выберите сообщение для редактирования.\n"
        "<b>✦</b> — кастомизированные.\n\n"
        "<i>Поддерживается HTML-разметка и плейсхолдеры:\n"
        "<code>{name}</code> — имя, <code>{style}</code> — стиль,\n"
        "<code>{e_welcome}</code> <code>{e_qr}</code> <code>{e_success}</code>... — эмодзи</i>",
        parse_mode="HTML", reply_markup=kb_msg_list())
    await callback.answer()


@dp.callback_query(F.data.startswith("txe_"))
async def cb_text_edit_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    key = callback.data[4:]
    if key not in DEFAULT_MSGS:
        await callback.answer("❌", show_alert=True); return
    admin_state[callback.from_user.id] = {"action": "set_text", "key": key}

    cfg = load_config()
    current = cfg.get("texts", {}).get(key) or DEFAULT_MSGS[key]
    # Экранируем < > для показа в HTML (превью кода)
    preview = current.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Обрезаем если слишком длинный
    if len(preview) > 500:
        preview = preview[:500] + "…"

    await callback.message.edit_text(
        f"📝 <b>{MSG_META[key]}</b>\n\n"
        f"Текущий текст:\n<code>{preview}</code>\n\n"
        f"Отправьте новый текст или <code>reset</code> для сброса.\n\n"
        f"<i>Плейсхолдеры: <code>{{name}}</code> <code>{{style}}</code> "
        f"<code>{{e_welcome}}</code> <code>{{e_qr}}</code> <code>{{e_success}}</code> "
        f"<code>{{e_error}}</code> <code>{{e_lock}}</code> <code>{{e_wait}}</code> "
        f"<code>{{styles_list}}</code> <code>{{success}}</code> <code>{{failed}}</code> "
        f"<code>{{total_users}}</code> <code>{{total_qr}}</code></i>",
        parse_mode="HTML",
        reply_markup=kb_back("design_texts"))
    await callback.answer()


@dp.callback_query(F.data == "txt_reset_msgs")
async def cb_texts_reset(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cfg = load_config(); cfg["texts"] = {}; save_config(cfg)
    await callback.message.edit_text(
        "✅ <b>Все тексты сообщений сброшены</b>",
        parse_mode="HTML", reply_markup=kb_back("design_texts"))
    await callback.answer()


# ═══════════════════════════════════════
#     CALLBACK — ТЕКСТЫ КНОПОК
# ═══════════════════════════════════════

@dp.callback_query(F.data == "design_buttons")
async def cb_buttons_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    admin_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "🔘 <b>Тексты кнопок</b>\n\n"
        "Выберите кнопку для редактирования.\n"
        "<b>✦</b> — кастомизированные.",
        parse_mode="HTML", reply_markup=kb_btn_list())
    await callback.answer()


@dp.callback_query(F.data.startswith("bte_"))
async def cb_btn_edit_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    key = callback.data[4:]
    if key not in DEFAULT_BTNS:
        await callback.answer("❌", show_alert=True); return
    admin_state[callback.from_user.id] = {"action": "set_btn", "key": key}

    cfg = load_config()
    current = cfg.get("buttons", {}).get(key) or DEFAULT_BTNS[key]

    await callback.message.edit_text(
        f"🔘 <b>{BTN_META[key]}</b>\n\n"
        f"Текущий текст: <code>{current}</code>\n\n"
        f"Отправьте новый текст кнопки или <code>reset</code> для сброса.",
        parse_mode="HTML",
        reply_markup=kb_back("design_buttons"))
    await callback.answer()


@dp.callback_query(F.data == "txt_reset_btns")
async def cb_btns_reset(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cfg = load_config(); cfg["buttons"] = {}; save_config(cfg)
    await callback.message.edit_text(
        "✅ <b>Все тексты кнопок сброшены</b>",
        parse_mode="HTML", reply_markup=kb_back("design_buttons"))
    await callback.answer()


# ═══════════════════════════════════════
#     CALLBACK — ЦВЕТА КНОПОК
# ═══════════════════════════════════════

@dp.callback_query(F.data == "design_colors")
async def cb_colors(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(
        "🎹 <b>Цвет кнопок</b>\n\n<b>✓</b> — текущий.\n\n"
        "<i>Требуется Telegram Bot API 8.1+</i>",
        parse_mode="HTML", reply_markup=kb_colors())
    await callback.answer()


@dp.callback_query(F.data.startswith("clr_"))
async def cb_color_set(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    ck = callback.data[4:]
    if ck not in BUTTON_COLORS: return
    cfg = load_config(); cfg["button_color"] = BUTTON_COLORS[ck]["value"]; save_config(cfg)
    await callback.message.edit_text(
        f"🎹 <b>Цвет обновлён:</b> {BUTTON_COLORS[ck]['name']}",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [mkbtn("🎹 Цвета", callback_data="design_colors")],
            [mkbtn(b("btn_back"), callback_data="admin_design")]
        ]))
    await callback.answer()


# ═══════════════════════════════════════
#     CALLBACK — КНОПКИ СТИЛЕЙ QR
# ═══════════════════════════════════════

@dp.callback_query(F.data == "design_style_btns")
async def cb_style_btns_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    admin_state.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "🎨 <b>Кнопки стилей QR</b>\n\n"
        "Выберите стиль для переименования кнопки.\n"
        "<b>✦</b> — кастомизированные.",
        parse_mode="HTML", reply_markup=kb_style_btn_list())
    await callback.answer()


@dp.callback_query(F.data == "stb_reset")
async def cb_style_btns_reset(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cfg = load_config(); cfg["style_names"] = {}; save_config(cfg)
    await callback.message.edit_text(
        "✅ <b>Все названия стилей сброшены</b>",
        parse_mode="HTML", reply_markup=kb_back("design_style_btns"))
    await callback.answer()


@dp.callback_query(F.data.startswith("stb_"))
async def cb_style_btn_edit(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    key = callback.data[4:]
    if key not in STYLES:
        await callback.answer("❌", show_alert=True); return
    admin_state[callback.from_user.id] = {"action": "set_style_btn", "key": key}
    cfg = load_config()
    current = cfg.get("style_names", {}).get(key) or STYLES[key]["name"]
    await callback.message.edit_text(
        f"🎨 <b>{STYLES[key]['name']}</b>\n\n"
        f"Текущее название кнопки: <code>{current}</code>\n\n"
        f"Отправьте новое название или <code>reset</code> для сброса.",
        parse_mode="HTML", reply_markup=kb_back("design_style_btns"))
    await callback.answer()


# ═══════════════════════════════════════
#     CALLBACK — СБРОС ВСЕГО
# ═══════════════════════════════════════

@dp.callback_query(F.data == "design_reset")
async def cb_reset_all(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cfg = load_config()
    cfg["emoji"] = {}; cfg["button_color"] = None
    cfg["texts"] = {}; cfg["buttons"] = {}; cfg["style_names"] = {}
    save_config(cfg)
    await callback.message.edit_text(
        "✅ <b>Всё оформление сброшено</b>\n\nЭмодзи, тексты, кнопки, цвета — по умолчанию.",
        parse_mode="HTML", reply_markup=kb_back("admin_design"))
    await callback.answer()


# ═══════════════════════════════════════
#     ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ
# ═══════════════════════════════════════

def extract_custom_emoji_id(message: Message) -> str | None:
    if not message.entities:
        return None
    for ent in message.entities:
        if ent.type == "custom_emoji":
            return ent.custom_emoji_id
    return None


@dp.message(F.text)
async def handle_text(message: Message):
    uid = message.from_user.id
    text = message.text.strip()
    state = admin_state.get(uid)

    # ═══ Админ: настройка эмодзи ═══
    if is_admin(uid) and state and state.get("action") == "set_emoji":
        key = state["key"]; admin_state.pop(uid, None)
        if text.lower() == "reset":
            cfg = load_config(); cfg.get("emoji", {}).pop(key, None); save_config(cfg)
            await message.answer(
                f"✅ Эмодзи <b>{EMOJI_KEYS[key]['label']}</b> сброшен.",
                parse_mode="HTML", reply_markup=kb_back("design_emoji"))
            return

        emoji_id = None
        m = re.match(r'^id[:\s]?(\d{5,})$', text)
        if m: emoji_id = m.group(1)
        if not emoji_id: emoji_id = extract_custom_emoji_id(message)
        if not emoji_id and text.isdigit() and len(text) > 5: emoji_id = text

        if not emoji_id:
            await message.answer(
                "❌ <b>Не найден премиум-эмодзи</b>\n\nОтправьте эмодзи или <code>id:ЧИСЛО</code>",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [mkbtn("🔄 Ещё раз", callback_data=f"emj_set_{key}")],
                    [mkbtn(b("btn_back"), callback_data="design_emoji")]
                ]))
            return

        fallback = EMOJI_KEYS[key]["default"]
        for ch in (message.text or ""):
            if ord(ch) > 127 and not ch.isdigit():
                fallback = ch; break

        cfg = load_config()
        cfg.setdefault("emoji", {})[key] = {"id": str(emoji_id), "fallback": fallback}
        save_config(cfg)
        await message.answer(
            f"✅ <b>Эмодзи обновлён!</b>\n\n"
            f"{EMOJI_KEYS[key]['label']}: id=<code>{emoji_id}</code>\nПревью: {e(key)}",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [mkbtn("😀 Ещё", callback_data="design_emoji")],
                [mkbtn(b("btn_back"), callback_data="admin_design")]
            ]))
        return

    # ═══ Админ: настройка текста сообщения ═══
    if is_admin(uid) and state and state.get("action") == "set_text":
        key = state["key"]; admin_state.pop(uid, None)
        if text.lower() == "reset":
            cfg = load_config(); cfg.get("texts", {}).pop(key, None); save_config(cfg)
            await message.answer(
                f"✅ Текст <b>{MSG_META[key]}</b> сброшен на стандартный.",
                parse_mode="HTML", reply_markup=kb_back("design_texts"))
            return
        cfg = load_config()
        cfg.setdefault("texts", {})[key] = text
        save_config(cfg)
        await message.answer(
            f"✅ <b>Текст обновлён!</b>\n\n"
            f"Сообщение: <b>{MSG_META[key]}</b>\n\n"
            f"<i>Превью (с подстановкой):</i>\n"
            f"{t(key, name='Имя', style='Стиль', success='0', failed='0', styles_list='...', total_users='0', total_qr='0')}",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [mkbtn("📝 Ещё", callback_data="design_texts")],
                [mkbtn(b("btn_back"), callback_data="admin_design")]
            ]))
        return

    # ═══ Админ: настройка текста кнопки ═══
    if is_admin(uid) and state and state.get("action") == "set_btn":
        key = state["key"]; admin_state.pop(uid, None)
        if text.lower() == "reset":
            cfg = load_config(); cfg.get("buttons", {}).pop(key, None); save_config(cfg)
            await message.answer(
                f"✅ Кнопка <b>{BTN_META[key]}</b> сброшена на стандартную.",
                parse_mode="HTML", reply_markup=kb_back("design_buttons"))
            return
        cfg = load_config()
        cfg.setdefault("buttons", {})[key] = text
        save_config(cfg)
        await message.answer(
            f"✅ <b>Кнопка обновлена!</b>\n\n"
            f"<b>{BTN_META[key]}</b> → <code>{text}</code>",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [mkbtn("🔘 Ещё", callback_data="design_buttons")],
                [mkbtn(b("btn_back"), callback_data="admin_design")]
            ]))
        return

    # ═══ Админ: переименование кнопки стиля QR ═══
    if is_admin(uid) and state and state.get("action") == "set_style_btn":
        key = state["key"]; admin_state.pop(uid, None)
        if text.lower() == "reset":
            cfg = load_config(); cfg.get("style_names", {}).pop(key, None); save_config(cfg)
            await message.answer(
                f"✅ Название стиля <b>{STYLES[key]['name']}</b> сброшено на стандартное.",
                parse_mode="HTML", reply_markup=kb_back("design_style_btns"))
            return
        cfg = load_config()
        cfg.setdefault("style_names", {})[key] = text
        save_config(cfg)
        await message.answer(
            f"✅ <b>Название стиля обновлено!</b>\n\n"
            f"<b>{STYLES[key]['name']}</b> → <code>{text}</code>",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [mkbtn("🎨 Ещё", callback_data="design_style_btns")],
                [mkbtn(b("btn_back"), callback_data="admin_design")]
            ]))
        return

    # ═══ Рассылка ═══
    if is_admin(uid) and uid in awaiting_broadcast:
        awaiting_broadcast.discard(uid)
        db = load_db()
        ok, fail = 0, 0
        for u in db:
            try:
                await bot.copy_message(int(u), uid, message.message_id); ok += 1
            except Exception:
                fail += 1
        await message.answer(
            t("msg_broadcast_done", success=ok, failed=fail),
            parse_mode="HTML", reply_markup=kb_main(admin=True))
        return

    # ═══ Проверка подписки ═══
    if not is_admin(uid) and not await is_subscribed(uid):
        await message.answer(t("msg_access_denied"), parse_mode="HTML", reply_markup=kb_sub())
        return

    # ═══ Генерация QR ═══
    if not text: return
    style = user_style.pop(uid, "dark_rounded")
    wait_msg = await message.answer(t("msg_generating"), parse_mode="HTML")
    try:
        qr_file = generate_qr(text, uid, style)
        photo = FSInputFile(qr_file)
        db = load_db()
        if str(uid) not in db: db[str(uid)] = {"qr_count": 0}
        db[str(uid)]["qr_count"] = db[str(uid)].get("qr_count", 0) + 1
        save_db(db)
        sn = STYLES.get(style, {}).get("name", "")
        await message.answer_photo(
            photo=photo, caption=t("msg_qr_ready", style=sn),
            parse_mode="HTML", reply_markup=kb_main(admin=is_admin(uid)))
        os.remove(qr_file)
    except Exception:
        await message.answer(
            t("msg_qr_error"), parse_mode="HTML", reply_markup=kb_main(admin=is_admin(uid)))
    finally:
        await wait_msg.delete()


# ═══════════════════════════════════════
#           QR ГЕНЕРАТОРЫ
# ═══════════════════════════════════════

def generate_qr(text, uid, style="dark_rounded"):
    g = {"dark_rounded": gen_dark_rounded, "classic": gen_classic,
         "dots": gen_dots, "gradient_blue": gen_gradient,
         "neon_green": gen_neon, "sunset": gen_sunset,
         "ocean": gen_ocean, "minimal": gen_minimal}
    return g.get(style, gen_dark_rounded)(text, uid)

def _make_matrix(text):
    qr = qrcode.QRCode(version=1, box_size=50, border=2)
    qr.add_data(text); qr.make(fit=True)
    return qr.get_matrix()

def _nb(matrix, sz, r, c, dr, dc):
    nr, nc = r+dr, c+dc
    return matrix[nr][nc] if 0 <= nr < sz and 0 <= nc < sz else False

def _draw_rounded(draw, m, sz, brd, ms, rad, bg, cfn):
    for row in range(sz):
        for col in range(sz):
            if not m[row][col]: continue
            x, y = (col+brd)*ms, (row+brd)*ms
            c = cfn(row, col, sz)
            tp = _nb(m,sz,row,col,-1,0); rt = _nb(m,sz,row,col,0,1)
            bt = _nb(m,sz,row,col,1,0); lt = _nb(m,sz,row,col,0,-1)
            draw.rectangle([(x,y),(x+ms,y+ms)], fill=c)
            if not tp and not lt:
                draw.rectangle([(x,y),(x+rad,y+rad)], fill=bg)
                draw.ellipse([(x,y),(x+rad*2,y+rad*2)], fill=c)
            if not tp and not rt:
                draw.rectangle([(x+ms-rad,y),(x+ms,y+rad)], fill=bg)
                draw.ellipse([(x+ms-rad*2,y),(x+ms,y+rad*2)], fill=c)
            if not bt and not rt:
                draw.rectangle([(x+ms-rad,y+ms-rad),(x+ms,y+ms)], fill=bg)
                draw.ellipse([(x+ms-rad*2,y+ms-rad*2),(x+ms,y+ms)], fill=c)
            if not bt and not lt:
                draw.rectangle([(x,y+ms-rad),(x+rad,y+ms)], fill=bg)
                draw.ellipse([(x,y+ms-rad*2),(x+rad*2,y+ms)], fill=c)

def _lerp(c1, c2, t):
    return tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))

def gen_dark_rounded(text, uid):
    m=_make_matrix(text); ms,brd,sz=50,2,len(m)
    img=Image.new('RGB',((sz+brd*2)*ms,)*2,(12,12,12))
    _draw_rounded(ImageDraw.Draw(img),m,sz,brd,ms,22,(12,12,12),lambda r,c,s:(255,255,255))
    f=f"qr_{uid}.png"; img.save(f); return f

def gen_classic(text, uid):
    m=_make_matrix(text); ms,brd,sz=50,2,len(m)
    img=Image.new('RGB',((sz+brd*2)*ms,)*2,(255,255,255)); d=ImageDraw.Draw(img)
    for r in range(sz):
        for c in range(sz):
            if m[r][c]:
                x,y=(c+brd)*ms,(r+brd)*ms; d.rectangle([(x,y),(x+ms,y+ms)],fill=(0,0,0))
    f=f"qr_{uid}.png"; img.save(f); return f

def gen_dots(text, uid):
    m=_make_matrix(text); ms,brd,sz=50,2,len(m)
    img=Image.new('RGB',((sz+brd*2)*ms,)*2,(245,245,250)); d=ImageDraw.Draw(img); rd=ms//2-3
    for r in range(sz):
        for c in range(sz):
            if m[r][c]:
                cx,cy=(c+brd)*ms+ms//2,(r+brd)*ms+ms//2
                d.ellipse([(cx-rd,cy-rd),(cx+rd,cy+rd)],fill=(30,60,180))
    f=f"qr_{uid}.png"; img.save(f); return f

def gen_gradient(text, uid):
    m=_make_matrix(text); ms,brd,sz=50,2,len(m); bg=(255,255,255)
    img=Image.new('RGB',((sz+brd*2)*ms,)*2,bg)
    _draw_rounded(ImageDraw.Draw(img),m,sz,brd,ms,20,bg,
        lambda r,c,s:_lerp((50,50,220),(180,50,220),(r+c)/(2*s) if s else 0))
    f=f"qr_{uid}.png"; img.save(f); return f

def gen_neon(text, uid):
    m=_make_matrix(text); ms,brd,sz=50,4,len(m); isz=(sz+brd*2)*ms; bg=(10,10,15)
    gl=Image.new('RGB',(isz,isz),bg); gd=ImageDraw.Draw(gl)
    for r in range(sz):
        for c in range(sz):
            if m[r][c]:
                x,y=(c+brd)*ms,(r+brd)*ms
                gd.rectangle([(x-8,y-8),(x+ms+8,y+ms+8)],fill=(0,255,100))
    gl=gl.filter(ImageFilter.GaussianBlur(18))
    img=Image.new('RGB',(isz,isz),bg); d=ImageDraw.Draw(img)
    for r in range(sz):
        for c in range(sz):
            if m[r][c]:
                x,y=(c+brd)*ms,(r+brd)*ms; d.rectangle([(x,y),(x+ms,y+ms)],fill=(180,255,200))
    img=ImageChops.lighter(gl,img)
    f=f"qr_{uid}.png"; img.save(f); return f

def gen_sunset(text, uid):
    m=_make_matrix(text); ms,brd,sz=50,2,len(m); bg=(255,250,245)
    img=Image.new('RGB',((sz+brd*2)*ms,)*2,bg)
    _draw_rounded(ImageDraw.Draw(img),m,sz,brd,ms,18,bg,
        lambda r,c,s:_lerp((255,100,50),(200,50,120),r/s if s else 0))
    f=f"qr_{uid}.png"; img.save(f); return f

def gen_ocean(text, uid):
    m=_make_matrix(text); ms,brd,sz=50,3,len(m)
    img=Image.new('RGB',((sz+brd*2)*ms,)*2,(15,20,35)); d=ImageDraw.Draw(img); rd=ms//2-2
    for r in range(sz):
        for c in range(sz):
            if m[r][c]:
                cx,cy=(c+brd)*ms+ms//2,(r+brd)*ms+ms//2
                tt=(r+c)/(2*sz) if sz else 0
                d.ellipse([(cx-rd,cy-rd),(cx+rd,cy+rd)],fill=_lerp((0,200,200),(0,100,220),tt))
    f=f"qr_{uid}.png"; img.save(f); return f

def gen_minimal(text, uid):
    m=_make_matrix(text); ms,brd,sz=50,3,len(m)
    img=Image.new('RGB',((sz+brd*2)*ms,)*2,(252,252,252)); d=ImageDraw.Draw(img); gap=6
    for r in range(sz):
        for c in range(sz):
            if m[r][c]:
                x,y=(c+brd)*ms+gap,(r+brd)*ms+gap; w=ms-gap*2
                d.rounded_rectangle([(x,y),(x+w,y+w)],radius=10,fill=(40,40,40))
    f=f"qr_{uid}.png"; img.save(f); return f


# ═══════════════════════════════════════
#           ЗАПУСК
# ═══════════════════════════════════════

async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
