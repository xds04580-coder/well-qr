import asyncio
import json
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
import qrcode
from PIL import Image, ImageDraw

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


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔲 Создать QR-код", callback_data="generate_qr")],
        [InlineKeyboardButton(text="📢 Наш канал", url=CHANNEL_URL)]
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🌐 Канал", url=CHANNEL_URL)]
    ])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
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

    if is_admin(user_id):
        await message.answer(
            f"👑 <b>Админ-панель</b>\n\n"
            f"Привет, <b>{name}</b>!\n"
            f"Управляй ботом через кнопки ниже.",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )
        return

    db = load_db()
    db[str(user_id)] = {"username": message.from_user.username, "name": name}
    save_db(db)

    if not await is_subscribed(user_id):
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
        f"🔲 Я умею генерировать <b>QR-коды</b> с красивыми закруглёнными углами.\n\n"
        f"Нажми кнопку ниже, чтобы начать 👇",
        parse_mode="HTML",
        reply_markup=main_keyboard()
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
            f"🔲 Я умею генерировать <b>QR-коды</b> с красивыми закруглёнными углами.\n\n"
            f"Нажми кнопку ниже, чтобы начать 👇",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
    else:
        await callback.answer("❌ Вы ещё не подписались на канал!", show_alert=True)


@dp.callback_query(F.data == "generate_qr")
async def ask_for_qr_text(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔲 <b>Генерация QR-кода</b>\n\n"
        "Отправьте ссылку или текст, который хотите закодировать:",
        parse_mode="HTML",
        reply_markup=back_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    if is_admin(callback.from_user.id):
        await callback.message.edit_text(
            "👑 <b>Админ-панель</b>",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )
    else:
        name = callback.from_user.first_name or "пользователь"
        await callback.message.edit_text(
            f"👋 Привет, <b>{name}</b>!\n\n"
            f"🔲 Я умею генерировать <b>QR-коды</b> с красивыми закруглёнными углами.\n\n"
            f"Нажми кнопку ниже, чтобы начать 👇",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
    await callback.answer()


# ═══════════════════════════════════════
#           CALLBACK — АДМИН
# ═══════════════════════════════════════

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    if callback.data == "admin_stats":
        db = load_db()
        total = len(db)
        await callback.message.edit_text(
            f"📊 <b>Статистика бота</b>\n\n"
            f"┌ 👥 Всего пользователей: <b>{total}</b>\n"
            f"└ 🤖 Бот работает в штатном режиме",
            parse_mode="HTML",
            reply_markup=back_keyboard()
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
            reply_markup=admin_keyboard()
        )
        return

    # Проверка подписки
    if not await is_subscribed(user_id):
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

    wait_msg = await message.answer("⏳ <b>Генерирую QR-код...</b>", parse_mode="HTML")

    try:
        qr_file = generate_qr(user_text, user_id)
        photo = FSInputFile(qr_file)
        await message.answer_photo(
            photo=photo,
            caption="✅ <b>QR-код готов!</b>\n\n"
                    "Нажми кнопку ниже чтобы создать ещё 👇",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        os.remove(qr_file)
    except Exception:
        await message.answer(
            "❌ <b>Ошибка при создании QR-кода</b>\n\nПопробуйте ещё раз.",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
    finally:
        await wait_msg.delete()


# ═══════════════════════════════════════
#           QR ГЕНЕРАТОР
# ═══════════════════════════════════════

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


# ═══════════════════════════════════════
#           ЗАПУСК
# ═══════════════════════════════════════

async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
