import asyncio
import json
import os
import math
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ═══════════════════════════════════════
#           КОНФИГУРАЦИЯ
# ═══════════════════════════════════════
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = -1003885905357
CHANNEL_URL = "https://t.me/WellUtility"
ADMIN_ID = 8369509247
DB_FILE = "users.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

awaiting_broadcast = set()
user_style = {}  # user_id -> selected style

# ═══════════════════════════════════════
#           СТИЛИ QR-КОДОВ
# ═══════════════════════════════════════

STYLES = {
    "dark_rounded": {
        "name": "🌑 Тёмный",
        "desc": "Тёмный фон, закруглённые модули"
    },
    "classic": {
        "name": "⬜ Классический",
        "desc": "Чёрно-белый стандартный"
    },
    "dots": {
        "name": "🔵 Точки",
        "desc": "Круглые модули"
    },
    "gradient_blue": {
        "name": "💎 Градиент",
        "desc": "Сине-фиолетовый градиент"
    },
    "neon_green": {
        "name": "💚 Неон",
        "desc": "Неоновое свечение на тёмном фоне"
    },
    "sunset": {
        "name": "🌅 Закат",
        "desc": "Оранжево-розовый градиент"
    },
    "ocean": {
        "name": "🌊 Океан",
        "desc": "Бирюзовые точки на тёмном фоне"
    },
    "minimal": {
        "name": "✨ Минимал",
        "desc": "Тонкие модули с большими промежутками"
    },
}


# ═══════════════════════════════════════
#           БАЗА ДАННЫХ
# ═══════════════════════════════════════

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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

def subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")]
    ])


def main_keyboard(is_admin_user: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔲 Создать QR-код", callback_data="generate_qr")],
        [InlineKeyboardButton(text="📢 Наш канал", url=CHANNEL_URL)],
    ]
    if is_admin_user:
        buttons.append([InlineKeyboardButton(text="👑 Админ-панель", callback_data="open_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def style_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    keys = list(STYLES.keys())
    for i in range(0, len(keys), 2):
        row = []
        for j in range(2):
            if i + j < len(keys):
                key = keys[i + j]
                row.append(InlineKeyboardButton(
                    text=STYLES[key]["name"],
                    callback_data=f"style_{key}"
                ))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🌐 Канал", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])


def back_keyboard(to_admin: bool = False) -> InlineKeyboardMarkup:
    target = "open_admin" if to_admin else "back_main"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=target)]
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
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
            f"👋 Привет, <b>{name}</b>!\n\n"
            f"🔒 Для использования бота необходимо подписаться на наш канал.\n\n"
            f"После подписки нажми <b>«Проверить подписку»</b>",
            parse_mode="HTML",
            reply_markup=subscription_keyboard()
        )
        return

    await message.answer(
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"🔲 Я умею генерировать <b>QR-коды</b> в разных стилях и дизайнах.\n\n"
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
            f"✅ <b>Подписка подтверждена!</b>\n\n"
            f"👋 Привет, <b>{name}</b>!\n\n"
            f"🔲 Я умею генерировать <b>QR-коды</b> в разных стилях и дизайнах.\n\n"
            f"Нажми кнопку ниже, чтобы начать 👇",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
    else:
        await callback.answer("❌ Вы ещё не подписались на канал!", show_alert=True)


@dp.callback_query(F.data == "generate_qr")
async def choose_style(callback: CallbackQuery):
    style_list = "\n".join(
        f"  {s['name']} — {s['desc']}" for s in STYLES.values()
    )
    await callback.message.edit_text(
        f"🎨 <b>Выберите стиль QR-кода:</b>\n\n{style_list}",
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
    style_name = STYLES[style_key]["name"]

    await callback.message.edit_text(
        f"🔲 <b>Генерация QR-кода</b>\n\n"
        f"Стиль: {style_name}\n\n"
        f"Отправьте ссылку или текст, который хотите закодировать:",
        parse_mode="HTML",
        reply_markup=back_keyboard(to_admin=False)
    )
    await callback.answer()


@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    user_style.pop(callback.from_user.id, None)
    name = callback.from_user.first_name or "пользователь"
    await callback.message.edit_text(
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"🔲 Я умею генерировать <b>QR-коды</b> в разных стилях и дизайнах.\n\n"
        f"Нажми кнопку ниже, чтобы начать 👇",
        parse_mode="HTML",
        reply_markup=main_keyboard(is_admin_user=is_admin(callback.from_user.id))
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
    await callback.message.edit_text(
        "👑 <b>Админ-панель</b>\n\n"
        "Выбери действие:",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    if callback.data == "admin_stats":
        db = load_db()
        total = len(db)
        total_qr = sum(u.get("qr_count", 0) for u in db.values())
        await callback.message.edit_text(
            f"📊 <b>Статистика бота</b>\n\n"
            f"┌ 👥 Всего пользователей: <b>{total}</b>\n"
            f"├ 🔲 QR-кодов сгенерировано: <b>{total_qr}</b>\n"
            f"└ 🤖 Бот работает в штатном режиме",
            parse_mode="HTML",
            reply_markup=back_keyboard(to_admin=True)
        )
        await callback.answer()

    elif callback.data == "admin_broadcast":
        awaiting_broadcast.add(callback.from_user.id)
        await callback.message.edit_text(
            "📢 <b>Рассылка</b>\n\n"
            "Отправьте сообщение, которое будет разослано всем пользователям.\n\n"
            "Поддерживается: текст, фото, видео, документы.",
            parse_mode="HTML",
            reply_markup=cancel_keyboard()
        )
        await callback.answer()


@dp.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery):
    awaiting_broadcast.discard(callback.from_user.id)
    await callback.message.edit_text(
        "👑 <b>Админ-панель</b>\n\n"
        "Рассылка отменена.",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )
    await callback.answer()


# ═══════════════════════════════════════
#           ОБРАБОТКА ТЕКСТА
# ═══════════════════════════════════════

@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id

    # Рассылка от админа
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
            f"📢 <b>Рассылка завершена</b>\n\n"
            f"┌ ✅ Доставлено: <b>{success}</b>\n"
            f"└ ❌ Ошибок: <b>{failed}</b>",
            parse_mode="HTML",
            reply_markup=main_keyboard(is_admin_user=True)
        )
        return

    # Проверка подписки для обычных пользователей
    if not is_admin(user_id) and not await is_subscribed(user_id):
        await message.answer(
            "🔒 <b>Доступ ограничен</b>\n\n"
            "Подпишитесь на канал для использования бота.",
            parse_mode="HTML",
            reply_markup=subscription_keyboard()
        )
        return

    # Генерация QR
    user_text = message.text.strip()
    if not user_text:
        return

    # Определяем стиль
    style = user_style.pop(user_id, "dark_rounded")

    wait_msg = await message.answer("⏳ <b>Генерирую QR-код...</b>", parse_mode="HTML")

    try:
        qr_file = generate_qr(user_text, user_id, style)
        photo = FSInputFile(qr_file)

        # Увеличиваем счётчик
        db = load_db()
        if str(user_id) not in db:
            db[str(user_id)] = {"qr_count": 0}
        db[str(user_id)]["qr_count"] = db[str(user_id)].get("qr_count", 0) + 1
        save_db(db)

        style_name = STYLES.get(style, {}).get("name", "")
        await message.answer_photo(
            photo=photo,
            caption=f"✅ <b>QR-код готов!</b>\n"
                    f"Стиль: {style_name}\n\n"
                    "Нажми кнопку ниже чтобы создать ещё 👇",
            parse_mode="HTML",
            reply_markup=main_keyboard(is_admin_user=is_admin(user_id))
        )
        os.remove(qr_file)
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при создании QR-кода</b>\n\nПопробуйте ещё раз.",
            parse_mode="HTML",
            reply_markup=main_keyboard(is_admin_user=is_admin(user_id))
        )
    finally:
        await wait_msg.delete()


# ═══════════════════════════════════════
#           QR ГЕНЕРАТОРЫ
# ═══════════════════════════════════════

def generate_qr(text, user_id, style="dark_rounded"):
    """Маршрутизатор стилей"""
    generators = {
        "dark_rounded": gen_dark_rounded,
        "classic": gen_classic,
        "dots": gen_dots,
        "gradient_blue": gen_gradient,
        "neon_green": gen_neon,
        "sunset": gen_sunset,
        "ocean": gen_ocean,
        "minimal": gen_minimal,
    }
    gen_func = generators.get(style, gen_dark_rounded)
    return gen_func(text, user_id)


def _make_matrix(text):
    """Общая функция для создания матрицы QR"""
    qr = qrcode.QRCode(version=1, box_size=50, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    return qr.get_matrix()


def _has_neighbor(matrix, size, row, col, dr, dc):
    nr, nc = row + dr, col + dc
    if 0 <= nr < size and 0 <= nc < size:
        return matrix[nr][nc]
    return False


# ───── 1. Тёмный с закруглёнными углами (оригинал) ─────

def gen_dark_rounded(text, user_id):
    matrix = _make_matrix(text)
    module_size = 50
    border = 2
    size = len(matrix)
    img_size = (size + border * 2) * module_size

    bg_color = (12, 12, 12)
    fg_color = (255, 255, 255)

    img = Image.new('RGB', (img_size, img_size), bg_color)
    draw = ImageDraw.Draw(img)
    radius = 22

    for row in range(size):
        for col in range(size):
            if matrix[row][col]:
                x = (col + border) * module_size
                y = (row + border) * module_size

                top = _has_neighbor(matrix, size, row, col, -1, 0)
                right = _has_neighbor(matrix, size, row, col, 0, 1)
                bottom = _has_neighbor(matrix, size, row, col, 1, 0)
                left = _has_neighbor(matrix, size, row, col, 0, -1)

                round_tl = not top and not left
                round_tr = not top and not right
                round_br = not bottom and not right
                round_bl = not bottom and not left

                draw.rectangle([(x, y), (x + module_size, y + module_size)], fill=fg_color)

                if round_tl:
                    draw.rectangle([(x, y), (x + radius, y + radius)], fill=bg_color)
                    draw.ellipse([(x, y), (x + radius * 2, y + radius * 2)], fill=fg_color)
                if round_tr:
                    draw.rectangle([(x + module_size - radius, y), (x + module_size, y + radius)], fill=bg_color)
                    draw.ellipse([(x + module_size - radius * 2, y), (x + module_size, y + radius * 2)], fill=fg_color)
                if round_br:
                    draw.rectangle([(x + module_size - radius, y + module_size - radius), (x + module_size, y + module_size)], fill=bg_color)
                    draw.ellipse([(x + module_size - radius * 2, y + module_size - radius * 2), (x + module_size, y + module_size)], fill=fg_color)
                if round_bl:
                    draw.rectangle([(x, y + module_size - radius), (x + radius, y + module_size)], fill=bg_color)
                    draw.ellipse([(x, y + module_size - radius * 2), (x + radius * 2, y + module_size)], fill=fg_color)

    filename = f"qr_{user_id}.png"
    img.save(filename)
    return filename


# ───── 2. Классический чёрно-белый ─────

def gen_classic(text, user_id):
    matrix = _make_matrix(text)
    module_size = 50
    border = 2
    size = len(matrix)
    img_size = (size + border * 2) * module_size

    img = Image.new('RGB', (img_size, img_size), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    for row in range(size):
        for col in range(size):
            if matrix[row][col]:
                x = (col + border) * module_size
                y = (row + border) * module_size
                draw.rectangle([(x, y), (x + module_size, y + module_size)], fill=(0, 0, 0))

    filename = f"qr_{user_id}.png"
    img.save(filename)
    return filename


# ───── 3. Точки (круглые модули) ─────

def gen_dots(text, user_id):
    matrix = _make_matrix(text)
    module_size = 50
    border = 2
    size = len(matrix)
    img_size = (size + border * 2) * module_size

    bg_color = (245, 245, 250)
    fg_color = (30, 60, 180)

    img = Image.new('RGB', (img_size, img_size), bg_color)
    draw = ImageDraw.Draw(img)

    dot_radius = module_size // 2 - 3

    for row in range(size):
        for col in range(size):
            if matrix[row][col]:
                cx = (col + border) * module_size + module_size // 2
                cy = (row + border) * module_size + module_size // 2
                draw.ellipse(
                    [(cx - dot_radius, cy - dot_radius),
                     (cx + dot_radius, cy + dot_radius)],
                    fill=fg_color
                )

    filename = f"qr_{user_id}.png"
    img.save(filename)
    return filename


# ───── 4. Градиент сине-фиолетовый ─────

def gen_gradient(text, user_id):
    matrix = _make_matrix(text)
    module_size = 50
    border = 2
    size = len(matrix)
    img_size = (size + border * 2) * module_size

    bg_color = (255, 255, 255)
    color_start = (50, 50, 220)   # синий
    color_end = (180, 50, 220)    # фиолетовый

    img = Image.new('RGB', (img_size, img_size), bg_color)
    draw = ImageDraw.Draw(img)
    radius = 20

    for row in range(size):
        for col in range(size):
            if matrix[row][col]:
                x = (col + border) * module_size
                y = (row + border) * module_size

                # Градиент по диагонали
                t = (row + col) / (2 * size) if size > 0 else 0
                r = int(color_start[0] + (color_end[0] - color_start[0]) * t)
                g = int(color_start[1] + (color_end[1] - color_start[1]) * t)
                b = int(color_start[2] + (color_end[2] - color_start[2]) * t)
                color = (r, g, b)

                top = _has_neighbor(matrix, size, row, col, -1, 0)
                right = _has_neighbor(matrix, size, row, col, 0, 1)
                bottom = _has_neighbor(matrix, size, row, col, 1, 0)
                left = _has_neighbor(matrix, size, row, col, 0, -1)

                round_tl = not top and not left
                round_tr = not top and not right
                round_br = not bottom and not right
                round_bl = not bottom and not left

                draw.rectangle([(x, y), (x + module_size, y + module_size)], fill=color)

                if round_tl:
                    draw.rectangle([(x, y), (x + radius, y + radius)], fill=bg_color)
                    draw.ellipse([(x, y), (x + radius * 2, y + radius * 2)], fill=color)
                if round_tr:
                    draw.rectangle([(x + module_size - radius, y), (x + module_size, y + radius)], fill=bg_color)
                    draw.ellipse([(x + module_size - radius * 2, y), (x + module_size, y + radius * 2)], fill=color)
                if round_br:
                    draw.rectangle([(x + module_size - radius, y + module_size - radius), (x + module_size, y + module_size)], fill=bg_color)
                    draw.ellipse([(x + module_size - radius * 2, y + module_size - radius * 2), (x + module_size, y + module_size)], fill=color)
                if round_bl:
                    draw.rectangle([(x, y + module_size - radius), (x + radius, y + module_size)], fill=bg_color)
                    draw.ellipse([(x, y + module_size - radius * 2), (x + radius * 2, y + module_size)], fill=color)

    filename = f"qr_{user_id}.png"
    img.save(filename)
    return filename


# ───── 5. Неон зелёный ─────

def gen_neon(text, user_id):
    matrix = _make_matrix(text)
    module_size = 50
    border = 4  # больше бордер для свечения
    size = len(matrix)
    img_size = (size + border * 2) * module_size

    bg_color = (10, 10, 15)
    glow_color = (0, 255, 100)
    core_color = (180, 255, 200)

    # Слой свечения
    glow_layer = Image.new('RGB', (img_size, img_size), bg_color)
    glow_draw = ImageDraw.Draw(glow_layer)

    # Рисуем увеличенные модули для свечения
    glow_expand = 8
    for row in range(size):
        for col in range(size):
            if matrix[row][col]:
                x = (col + border) * module_size
                y = (row + border) * module_size
                glow_draw.rectangle(
                    [(x - glow_expand, y - glow_expand),
                     (x + module_size + glow_expand, y + module_size + glow_expand)],
                    fill=glow_color
                )

    # Блюр для свечения
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=18))

    # Основной слой
    img = Image.new('RGB', (img_size, img_size), bg_color)
    draw = ImageDraw.Draw(img)

    for row in range(size):
        for col in range(size):
            if matrix[row][col]:
                x = (col + border) * module_size
                y = (row + border) * module_size
                draw.rectangle([(x, y), (x + module_size, y + module_size)], fill=core_color)

    # Совмещаем: берём max(glow, основной)
    from PIL import ImageChops
    img = ImageChops.lighter(glow_layer, img)

    filename = f"qr_{user_id}.png"
    img.save(filename)
    return filename


# ───── 6. Закат ─────

def gen_sunset(text, user_id):
    matrix = _make_matrix(text)
    module_size = 50
    border = 2
    size = len(matrix)
    img_size = (size + border * 2) * module_size

    bg_color = (255, 250, 245)
    color_top = (255, 100, 50)     # оранжевый
    color_bottom = (200, 50, 120)  # розовый

    img = Image.new('RGB', (img_size, img_size), bg_color)
    draw = ImageDraw.Draw(img)
    radius = 18

    for row in range(size):
        for col in range(size):
            if matrix[row][col]:
                x = (col + border) * module_size
                y = (row + border) * module_size

                t = row / size if size > 0 else 0
                r = int(color_top[0] + (color_bottom[0] - color_top[0]) * t)
                g = int(color_top[1] + (color_bottom[1] - color_top[1]) * t)
                b = int(color_top[2] + (color_bottom[2] - color_top[2]) * t)
                color = (r, g, b)

                top = _has_neighbor(matrix, size, row, col, -1, 0)
                right = _has_neighbor(matrix, size, row, col, 0, 1)
                bottom = _has_neighbor(matrix, size, row, col, 1, 0)
                left = _has_neighbor(matrix, size, row, col, 0, -1)

                round_tl = not top and not left
                round_tr = not top and not right
                round_br = not bottom and not right
                round_bl = not bottom and not left

                draw.rectangle([(x, y), (x + module_size, y + module_size)], fill=color)

                if round_tl:
                    draw.rectangle([(x, y), (x + radius, y + radius)], fill=bg_color)
                    draw.ellipse([(x, y), (x + radius * 2, y + radius * 2)], fill=color)
                if round_tr:
                    draw.rectangle([(x + module_size - radius, y), (x + module_size, y + radius)], fill=bg_color)
                    draw.ellipse([(x + module_size - radius * 2, y), (x + module_size, y + radius * 2)], fill=color)
                if round_br:
                    draw.rectangle([(x + module_size - radius, y + module_size - radius), (x + module_size, y + module_size)], fill=bg_color)
                    draw.ellipse([(x + module_size - radius * 2, y + module_size - radius * 2), (x + module_size, y + module_size)], fill=color)
                if round_bl:
                    draw.rectangle([(x, y + module_size - radius), (x + radius, y + module_size)], fill=bg_color)
                    draw.ellipse([(x, y + module_size - radius * 2), (x + radius * 2, y + module_size)], fill=color)

    filename = f"qr_{user_id}.png"
    img.save(filename)
    return filename


# ───── 7. Океан (бирюзовые точки на тёмном) ─────

def gen_ocean(text, user_id):
    matrix = _make_matrix(text)
    module_size = 50
    border = 3
    size = len(matrix)
    img_size = (size + border * 2) * module_size

    bg_color = (15, 20, 35)
    color_start = (0, 200, 200)   # бирюзовый
    color_end = (0, 100, 220)     # глубокий синий

    img = Image.new('RGB', (img_size, img_size), bg_color)
    draw = ImageDraw.Draw(img)

    dot_radius = module_size // 2 - 2

    for row in range(size):
        for col in range(size):
            if matrix[row][col]:
                cx = (col + border) * module_size + module_size // 2
                cy = (row + border) * module_size + module_size // 2

                t = (row + col) / (2 * size) if size > 0 else 0
                r = int(color_start[0] + (color_end[0] - color_start[0]) * t)
                g = int(color_start[1] + (color_end[1] - color_start[1]) * t)
                b = int(color_start[2] + (color_end[2] - color_start[2]) * t)

                draw.ellipse(
                    [(cx - dot_radius, cy - dot_radius),
                     (cx + dot_radius, cy + dot_radius)],
                    fill=(r, g, b)
                )

    filename = f"qr_{user_id}.png"
    img.save(filename)
    return filename


# ───── 8. Минимал (тонкие модули с промежутками) ─────

def gen_minimal(text, user_id):
    matrix = _make_matrix(text)
    module_size = 50
    border = 3
    size = len(matrix)
    img_size = (size + border * 2) * module_size

    bg_color = (252, 252, 252)
    fg_color = (40, 40, 40)

    img = Image.new('RGB', (img_size, img_size), bg_color)
    draw = ImageDraw.Draw(img)

    gap = 6  # промежуток между модулями
    corner_radius = 10

    for row in range(size):
        for col in range(size):
            if matrix[row][col]:
                x = (col + border) * module_size + gap
                y = (row + border) * module_size + gap
                w = module_size - gap * 2
                h = module_size - gap * 2

                # Рисуем скруглённый прямоугольник
                draw.rounded_rectangle(
                    [(x, y), (x + w, y + h)],
                    radius=corner_radius,
                    fill=fg_color
                )

    filename = f"qr_{user_id}.png"
    img.save(filename)
    return filename


# ═══════════════════════════════════════
#           ЗАПУСК
# ═══════════════════════════════════════

async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
