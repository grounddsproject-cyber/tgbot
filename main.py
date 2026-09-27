import asyncio
import json
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession

# ==================== НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ====================
TOKEN_TELEGRAM = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
ADMIN_TG_ID = int(os.getenv("ADMIN_TG_ID", "123456789"))

# ==================== КОНСТАНТЫ ====================
SERVERS = ["The bruh Land", "Пивные дали", "Движуха"]

STATUS_NAMES = {
    1: "Технические работы",
    2: "Сервер работает",
    3: "Сервер остановлен",
    4: "Остановлен [по запросу]",
    5: "Неизвестно",
}

STATUS_FILE = "statuses.json"
REPORTS_FILE = "reports.json"

# ==================== ХРАНИЛИЩЕ ====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Инициализация статусов
statuses = load_json(STATUS_FILE, {s: {"status": 5, "note": ""} for s in SERVERS})
for s in SERVERS:
    if s not in statuses:
        statuses[s] = {"status": 5, "note": ""}
save_json(STATUS_FILE, statuses)

# ==================== TELEGRAM BOT ====================
# Если на хостинге будет ошибка подключения к Telegram, раскомментируй строки ниже
# и вставь свой прокси (можно взять на proxy6.net или proxy.sale)

# proxy_url = "http://login:password@ip:port"  # Замени на свои данные!
# session = AiohttpSession(proxy=proxy_url)
# bot = Bot(token=TOKEN_TELEGRAM, session=session)

bot = Bot(token=TOKEN_TELEGRAM)
dp = Dispatcher(storage=MemoryStorage())


class NoteStates(StatesGroup):
    waiting_note = State()


async def build_main_menu():
    """Главное меню с выбором сервера"""
    buttons = []
    for server in SERVERS:
        data = statuses.get(server, {"status": 5})
        status_name = STATUS_NAMES.get(data["status"], "Неизвестно")
        buttons.append([InlineKeyboardButton(
            text=f"{server} [{status_name}]",
            callback_data=f"srv:{server}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def build_server_menu(server: str):
    """Меню управления конкретным сервером"""
    data = statuses.get(server, {"status": 5, "note": ""})
    buttons = []
    for code, name in STATUS_NAMES.items():
        mark = "✅ " if code == data["status"] else ""
        buttons.append([InlineKeyboardButton(
            text=f"{mark}{name}",
            callback_data=f"set:{server}:{code}"
        )])
    buttons.append([InlineKeyboardButton(
        text="📝 Изменить заметку" if data.get("note") else "📝 Добавить заметку",
        callback_data=f"note:{server}"
    )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def check_reports():
    """Периодически проверяет новые жалобы из reports.json"""
    last_report_count = len(load_json(REPORTS_FILE, []))
    
    while True:
        await asyncio.sleep(5)
        try:
            reports = load_json(REPORTS_FILE, [])
            if len(reports) > last_report_count:
                new_reports = reports[last_report_count:]
                for report in new_reports:
                    await bot.send_message(
                        ADMIN_TG_ID,
                        f"🚨 <b>Поступила жалоба на подключение!</b>\n\n"
                        f"Пользователь: <b>{report['user']}</b>\n"
                        f"Сервер Discord: <b>{report['guild']}</b>\n"
                        f"Время: {report['time']}",
                        parse_mode="HTML"
                    )
                last_report_count = len(reports)
                logging.info(f"Отправлено {len(new_reports)} новых жалоб")
        except Exception as e:
            logging.error(f"Ошибка проверки жалоб: {e}")


@dp.message(CommandStart())
async def start_handler(message: Message):
    if message.from_user.id != ADMIN_TG_ID:
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "👋 <b>Панель управления серверами</b>\n\n"
        "Выберите сервер для управления:",
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
            "👋 <b>Панель управления серверами</b>\n\nВыберите сервер:",
            reply_markup=await build_main_menu(),
            parse_mode="HTML"
        )
        await callback.answer()

    elif data.startswith("srv:"):
        server = data[4:]
        server_data = statuses.get(server, {"status": 5, "note": ""})
        await callback.message.edit_text(
            f"🖥 <b>{server}</b>\n\n"
            f"Текущий статус: <b>{STATUS_NAMES.get(server_data['status'], 'Неизвестно')}</b>\n"
            f"Заметка: <i>{server_data.get('note') or '—'}</i>\n\n"
            "Выберите новый статус:",
            reply_markup=await build_server_menu(server),
            parse_mode="HTML"
        )
        await callback.answer()

    elif data.startswith("set:"):
        _, server, code = data.split(":")
        code = int(code)
        statuses[server]["status"] = code
        save_json(STATUS_FILE, statuses)
        
        server_data = statuses.get(server, {"status": 5, "note": ""})
        await callback.message.edit_text(
            f"🖥 <b>{server}</b>\n\n"
            f"Текущий статус: <b>{STATUS_NAMES.get(code, 'Неизвестно')}</b>\n"
            f"Заметка: <i>{server_data.get('note') or '—'}</i>\n\n"
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
    if text == "-":
        statuses[server]["note"] = ""
    else:
        statuses[server]["note"] = text
    save_json(STATUS_FILE, statuses)
    await state.clear()

    await message.answer(
        f"✅ Заметка для <b>{server}</b> обновлена.",
        reply_markup=await build_server_menu(server),
        parse_mode="HTML"
    )


async def main():
    # Запускаем проверку жалоб в фоне
    asyncio.create_task(check_reports())
    
    # Запускаем бота
    logging.info("Telegram бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Telegram бот остановлен.")