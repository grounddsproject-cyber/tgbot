import asyncio
import os
import logging
import asyncpg
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ==================== НАСТРОЙКИ ====================
TOKEN_TELEGRAM = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
ADMIN_TG_ID = int(os.getenv("ADMIN_TG_ID", "123456789"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@db.xxx.supabase.co:5432/postgres")

SERVERS = ["The bruh Land", "Пивные дали", "Движуха"]

STATUS_NAMES = {
    1: "Технические работы",
    2: "Сервер работает",
    3: "Сервер остановлен",
    4: "Остановлен [по запросу]",
    5: "Неизвестно",
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==================== БАЗА ДАННЫХ ====================
db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    logging.info("Подключение к БД установлено")

async def get_server(server_name):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status, note FROM servers WHERE name = $1", server_name)
        return dict(row) if row else {"status": 5, "note": ""}

async def get_all_servers():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT name, status, note FROM servers ORDER BY id")
        return [dict(r) for r in rows]

async def set_status(server_name, status):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE servers SET status = $1 WHERE name = $2", status, server_name)

async def set_note(server_name, note):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE servers SET note = $1 WHERE name = $2", note, server_name)

async def get_unread_reports():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, user_name, guild_name, created_at FROM reports WHERE is_read = FALSE ORDER BY id")
        return [dict(r) for r in rows]

async def mark_reports_read(ids):
    if not ids:
        return
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE reports SET is_read = TRUE WHERE id = ANY($1::int[])", ids)

# ==================== TELEGRAM BOT ====================
bot = Bot(token=TOKEN_TELEGRAM)
dp = Dispatcher(storage=MemoryStorage())


class NoteStates(StatesGroup):
    waiting_note = State()


async def build_main_menu():
    servers = await get_all_servers()
    buttons = []
    for s in servers:
        status_name = STATUS_NAMES.get(s["status"], "Неизвестно")
        buttons.append([InlineKeyboardButton(
            text=f"{s['name']} [{status_name}]",
            callback_data=f"srv:{s['name']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def build_server_menu(server_name: str):
    data = await get_server(server_name)
    buttons = []
    for code, name in STATUS_NAMES.items():
        mark = "✅ " if code == data["status"] else ""
        buttons.append([InlineKeyboardButton(
            text=f"{mark}{name}",
            callback_data=f"set:{server_name}:{code}"
        )])
    buttons.append([InlineKeyboardButton(
        text="📝 Изменить заметку" if data.get("note") else "📝 Добавить заметку",
        callback_data=f"note:{server_name}"
    )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def check_reports():
    """Проверяет новые жалобы каждые 5 секунд"""
    await asyncio.sleep(3)  # Даём время на инициализацию
    
    while True:
        try:
            reports = await get_unread_reports()
            if reports:
                ids = []
                for r in reports:
                    await bot.send_message(
                        ADMIN_TG_ID,
                        f"🚨 <b>Жалоба на подключение!</b>\n\n"
                        f"Пользователь: <b>{r['user_name']}</b>\n"
                        f"Сервер: <b>{r['guild_name']}</b>\n"
                        f"Время: {r['created_at'].strftime('%d.%m.%Y %H:%M:%S')}",
                        parse_mode="HTML"
                    )
                    ids.append(r["id"])
                await mark_reports_read(ids)
                logging.info(f"Отправлено {len(reports)} жалоб")
        except Exception as e:
            logging.error(f"Ошибка проверки жалоб: {e}")
        
        await asyncio.sleep(5)


@dp.message(CommandStart())
async def start_handler(message: Message):
    if message.from_user.id != ADMIN_TG_ID:
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "👋 <b>Панель управления серверами</b>\n\nВыберите сервер:",
        reply_markup=await build_main_menu(),
        parse_mode="HTML"
    )


@dp.callback_query()
async def callback_handler(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_TG_ID:
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    data = callback.data

    if data == "back:main":
        await state.clear()
        await callback.message.edit_text(
            "👋 <b>Панель управления</b>\n\nВыберите сервер:",
            reply_markup=await build_main_menu(),
            parse_mode="HTML"
        )
        await callback.answer()

    elif data.startswith("srv:"):
        server = data[4:]
        s_data = await get_server(server)
        await callback.message.edit_text(
            f"🖥 <b>{server}</b>\n\n"
            f"Статус: <b>{STATUS_NAMES.get(s_data['status'], 'Неизвестно')}</b>\n"
            f"Заметка: <i>{s_data.get('note') or '—'}</i>\n\n"
            "Выберите новый статус:",
            reply_markup=await build_server_menu(server),
            parse_mode="HTML"
        )
        await callback.answer()

    elif data.startswith("set:"):
        _, server, code = data.split(":")
        code = int(code)
        await set_status(server, code)
        s_data = await get_server(server)
        await callback.message.edit_text(
            f"🖥 <b>{server}</b>\n\n"
            f"Статус: <b>{STATUS_NAMES.get(code, 'Неизвестно')}</b>\n"
            f"Заметка: <i>{s_data.get('note') or '—'}</i>\n\n"
            "Выберите новый статус:",
            reply_markup=await build_server_menu(server),
            parse_mode="HTML"
        )
        await callback.answer("✅ Статус обновлён")

    elif data.startswith("note:"):
        server = data[5:]
        await state.update_data(server=server)
        await state.set_state(NoteStates.waiting_note)
        await callback.message.edit_text(
            f"📝 Введите новую заметку для <b>{server}</b>:\n"
            f"(отправьте <code>-</code> чтобы удалить заметку)",
            parse_mode="HTML"
        )
        await callback.answer()


@dp.message(NoteStates.waiting_note)
async def note_handler(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_TG_ID:
        return
    data = await state.get_data()
    server = data.get("server")
    if not server:
        await state.clear()
        return

    text = message.text.strip()
    note = "" if text == "-" else text
    await set_note(server, note)
    await state.clear()

    await message.answer(
        f"✅ Заметка для <b>{server}</b> обновлена.",
        reply_markup=await build_server_menu(server),
        parse_mode="HTML"
    )


async def main():
    await init_db()
    asyncio.create_task(check_reports())
    logging.info("Telegram бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Telegram бот остановлен.")
