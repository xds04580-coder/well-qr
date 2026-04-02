import asyncio
import json
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
import qrcode
from PIL import Image, ImageDraw

# Конфигурация
TOKEN = 8796049629:AAFq73Ns2Psck30-KXNgAQZuMT4ERbdQQy0
CHANNEL_ID = -1003885905357
ADMIN_ID = 8369509247  # ← вставь свой Telegram ID
DB_FILE = "users.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Флаг ожидания рассылки
awaiting_broadcast = set()


# ─── База данных ───────────────────────────────────────────────

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── Проверки ──────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        return False


# ─── Клавиатуры ────────────────────────────────────────────────

def subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
    ])


# ─── /start ───────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id

    if is_admin(user_id):
        await message.answer(
            "<blockquote><b>👑 Админ-панель</b></blockquote>",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )
        return

    db = load_db()
    db[str(user_id)] = {"username": message.from_user.username}
    save_db(db)

    if not await is_subscribed(user_id):
        await message.answer(
            "<blockquote><b>Для использования бота необходимо подписаться на канал</b></blockquote>",
            parse_mode="HTML",
            reply_markup=subscription_keyboard()
        )
        return

    await message.answer(
        "<blockquote><b>Отправьте ссылку для генерации QR-кода</b></blockquote>",
        parse_mode="HTML"
    )


# ─── /admin ───────────────────────────────────────────────────

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "<blockquote><b>👑 Админ-панель</b></blockquote>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ─── Callback админ-панели ────────────────────────────────────

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    if callback.data == "admin_stats":
        db = load_db()
        total = len(db)
        await callback.message.answer(
            f"<blockquote><b>📊 Статистика</b>\n\n"
            f"👥 Всего пользователей: <b>{total}</b></blockquote>",
            parse_mode="HTML"
        )
        await callback.answer()

    elif callback.data == "admin_broadcast":
        awaiting_broadcast.add(callback.from_user.id)
        await callback.message.answer("📢 Отправьте сообщение для рассылки:")
        await callback.answer()


# ─── Callback проверки подписки ───────────────────────────────

@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "<blockquote><b>Отправьте ссылку для генерации QR-кода</b></blockquote>",
            parse_mode="HTML"
        )
    else:
        await callback.answer("Вы ещё не подписались на канал!", show_alert=True)


# ─── Обработка сообщений ──────────────────────────────────────

@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id

    # Рассылка
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
            f"<blockquote>📢 Рассылка завершена\n\n"
            f"✅ Доставлено: <b>{success}</b>\n"
            f"❌ Ошибок: <b>{failed}</b></blockquote>",
            parse_mode="HTML"
        )
        return

    # Обычный пользователь
    if not await is_subscribed(user_id):
        await message.answer(
            "<blockquote><b>Для использования бота необходимо подписаться на канал</b></blockquote>",
            parse_mode="HTML",
            reply_markup=subscription_keyboard()
        )
        return

    user_text = message.text.strip()
    if not user_text:
        return

    try:
        qr_file = generate_qr(user_text, user_id)
        photo = FSInputFile(qr_file)
        await message.answer_photo(photo=photo)
        os.remove(qr_file)
    except Exception:
        await message.answer("Ошибка при создании QR-кода")


# ─── QR генератор ─────────────────────────────────────────────

def generate_qr(text, user_id):
    qr = qrcode.QRCode(version=1, box_size=50, border=2)
    qr.add_data(text)
    qr.make(fit=True)

    matrix = qr.get_matrix()
    module_size = 50
    border = 2
    size = len(matrix)
    img_size = (size + border * 2) * module_size

    img = Image.new('RGB', (img_size, img_size), (12, 12, 12))
    draw = ImageDraw.Draw(img)
    radius = 22

    def has_neighbor(row, col, dr, dc):
        nr, nc = row + dr, col + dc
        if 0 <= nr < size and 0 <= nc < size:
            return matrix[nr][nc]
        return False

    for row in range(size):
        for col in range(size):
            if matrix[row][col]:
                x = (col + border) * module_size
                y = (row + border) * module_size

                top = has_neighbor(row, col, -1, 0)
                right = has_neighbor(row, col, 0, 1)
                bottom = has_neighbor(row, col, 1, 0)
                left = has_neighbor(row, col, 0, -1)

                round_tl = not top and not left
                round_tr = not top and not right
                round_br = not bottom and not right
                round_bl = not bottom and not left

                draw.rectangle([(x, y), (x + module_size, y + module_size)], fill='white')

                if round_tl:
                    draw.rectangle([(x, y), (x + radius, y + radius)], fill=(12, 12, 12))
                    draw.ellipse([(x, y), (x + radius * 2, y + radius * 2)], fill='white')
                if round_tr:
                    draw.rectangle([(x + module_size - radius, y), (x + module_size, y + radius)], fill=(12, 12, 12))
                    draw.ellipse([(x + module_size - radius * 2, y), (x + module_size, y + radius * 2)], fill='white')
                if round_br:
                    draw.rectangle([(x + module_size - radius, y + module_size - radius), (x + module_size, y + module_size)], fill=(12, 12, 12))
                    draw.ellipse([(x + module_size - radius * 2, y + module_size - radius * 2), (x + module_size, y + module_size)], fill='white')
                if round_bl:
                    draw.rectangle([(x, y + module_size - radius), (x + radius, y + module_size)], fill=(12, 12, 12))
                    draw.ellipse([(x, y + module_size - radius * 2), (x + radius * 2, y + module_size)], fill='white')

    filename = f"qr_{user_id}.png"
    img.save(filename)
    return filename


# ─── Запуск ───────────────────────────────────────────────────

async def main():
    print("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
