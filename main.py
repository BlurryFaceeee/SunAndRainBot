import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters.callback_data import CallbackData
from config import BOT_TOKEN, WEATHER_TOKEN
import requests
import asyncio
from datetime import timedelta, datetime
import sqlite3
from database import init_db, add_notification, get_all_user_notifications, delete_notification, \
    toggle_notification_status, get_notifications_to_send
from scheduler import get_weather
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
import re
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def init_db():
    conn = sqlite3.connect('notifications.db')
    conn.create_function("time", 2, lambda time, offset:
        (datetime.strptime(time, "%H:%M") +
         timedelta(hours=float(offset))).strftime("%H:%M"))
    conn = sqlite3.connect('notifications.db')
    cursor = conn.cursor()

    cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                city TEXT NOT NULL,
                notification_time TEXT NOT NULL,  
                timezone_offset TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
    conn.commit()
    conn.close()

class WeatherNotification(StatesGroup):
    waiting_for_city = State()
    waiting_for_time = State()
    waiting_for_timezone = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

@dp.message(Command("add_weather_notif"))
async def add_weather_notif_handler(message: Message, state: FSMContext):
    await message.answer("Пожалуйста, введи город\nНапример: 'Москва'")
    await state.set_state(WeatherNotification.waiting_for_city)


@dp.message(StateFilter(WeatherNotification.waiting_for_city))
async def process_city(message: Message, state: FSMContext):
    city = message.text
    try:
        response = requests.get(
            f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_TOKEN}&units=metric&lang=ru"
        )
        data = response.json()
        if data.get("cod") != 200:  # Если город не найден
            await message.reply("❌ Город не найден... Попробуй ещё раз")
            return

        await state.update_data(city=city)
        await message.answer("✅ Город принят! Теперь введи время уведомления в формате ЧЧ:ММ (например, 12:30)")
        await state.set_state(WeatherNotification.waiting_for_time)
    except requests.exceptions.RequestException:
        await message.reply("❌ Ошибка при проверке города... Попробуй позже")


@dp.message(StateFilter(WeatherNotification.waiting_for_time))
async def process_time(message: Message, state: FSMContext):
    time_input = message.text
    if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', time_input):
        await message.reply("❌ Неверный формат времени... Введи в формате ЧЧ:ММ (например, 09:30)")
        return

    await state.update_data(notification_time=time_input)
    await message.answer(
        "✅ Время принято! Теперь введи своё текущее время в формате ЧЧ:ММ (для определения часового пояса)")
    await state.set_state(WeatherNotification.waiting_for_timezone)

@dp.message(StateFilter(WeatherNotification.waiting_for_timezone))
async def process_timezone(message: Message, state: FSMContext):
    try:
        user_time_input = message.text
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', user_time_input):
            await message.reply("❌ Неверный формат... Введи время в формате ЧЧ:ММ")
            return

        data = await state.get_data()
        notification_time = data[
            'notification_time']

        bot_time_now = datetime.now().strftime("%H:%M")

        def time_to_minutes(t):
            h, m = map(int, t.split(':'))
            return h * 60 + m

        user_min = time_to_minutes(user_time_input)
        bot_min = time_to_minutes(bot_time_now)
        notification_min = time_to_minutes(notification_time)

        time_diff = user_min - bot_min

        bot_notification_min = notification_min - time_diff

        h = bot_notification_min // 60
        m = bot_notification_min % 60
        bot_notification_time = f"{h:02d}:{m:02d}"

        add_notification(
            user_id=message.from_user.id,
            city=data['city'],
            notification_time=bot_notification_time,
            timezone_offset=str(time_diff / 60)
        )

        await message.answer(
            f"✅ Уведомление создано!\n"
            f"Город: {data['city']} | Время: {notification_time}"
        )
        await state.clear()

    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


def format_weather_message(weather_data):
    pass

async def send_weather_notifications(now_utc=None):
    current_time = datetime.now().strftime("%H:%M")

    notifications = get_notifications_to_send()

    for user_id, city, notification_time, _ in notifications:
        try:

            if current_time == notification_time:
                response = requests.get(
                    f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_TOKEN}&units=metric&lang=ru"
                )
                data = response.json()

                if data.get("cod") == 200:
                    code_to_smile = {
                        "Clear": "ясно ☀️",
                        "Clouds": "облачно ☁️",
                        "Rain": "дождь 🌧",
                        "Drizzle": "дождь 🌧",
                        "Thunderstorm": "гроза ⚡️",
                        "Snow": "снег 🌨️",
                        "Mist": "туман 🌫"
                    }

                    city = data["name"]
                    cur_weather = data["main"]["temp"]
                    description = data["weather"][0]["main"]

                    wd = code_to_smile.get(description, "Посмотри в окно, не могу понять что там за погода...🤷")

                    cur = cur_weather
                    if cur <= -15:
                        cur = "мороз"
                    elif cur > -15 and cur <= 8:
                        cur = "холодно"
                    elif cur > 8 and cur <= 23:
                        cur = "тепло"
                    elif cur >= 23:
                        cur = "жарко"

                    await bot.send_message(
                        user_id,f"Сейчас в городе {city} {cur_weather} C°\nНа улице {cur}, {wd}")

                    weather_data = get_weather(city)
                    await bot.send_message(user_id, format_weather_message(weather_data))

        except Exception as e:
            print(f"Ошибка при отправке уведомления: {e}")

class NotificationCallback(CallbackData, prefix="notif"):
    action: str  # 'delete', 'toggle'
    notif_id: int

@dp.message(Command("my_weather_notif"))
async def show_user_notifications(message: Message):
    user_id = message.from_user.id
    notifications = get_all_user_notifications(user_id)

    if not notifications:
        await message.answer("У тебя нет активных уведомлений")
        return

    await message.answer("Твои активные уведомления:")

    for notif_id, city, user_time, is_active in notifications:
        notification_text = f"Город: {city} | Время: {user_time}"

        if not is_active:
            notification_text += f"\nСтатус: Приостановлено ⏸"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏸ Остановить" if is_active else "▶️ Возобновить",
                    callback_data=f"notif:toggle:{notif_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Удалить",
                    callback_data=f"notif:delete:{notif_id}"
                )
            ]
        ])

        await message.answer(
            text=notification_text,
            reply_markup=keyboard
        )


@dp.callback_query(F.data.startswith("notif:"))
async def handle_notification_actions(callback: CallbackQuery):
    action, notif_id = callback.data.split(":")[1:]
    notif_id = int(notif_id)

    if action == "delete":
        delete_notification(notif_id)
        await callback.message.edit_text(
            text=f"{callback.message.text}\nУведомление удалено",
            reply_markup=None
        )
    elif action == "toggle":
        new_status = toggle_notification_status(notif_id)

        message_text = callback.message.text.split('\n')[0]
        if new_status:
            message_text = message_text.split('\nСтатус:')[0]
        else:
            message_text += f"\nСтатус: Приостановлено"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏸ Остановить" if new_status else "▶️ Возобновить",
                    callback_data=f"notif:toggle:{notif_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Удалить",
                    callback_data=f"notif:delete:{notif_id}"
                )
            ]
        ])

        await callback.message.edit_text(
            text=message_text,
            reply_markup=keyboard
        )

    await callback.answer()

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет!👋\nНапиши мне название города, а я пришлю погоду!😊")

@dp.message(F.text)
async def weather_handler(message: Message):
    code_to_smile = {
        "Clear": "ясно ☀️",
        "Clouds": "облачно ☁️",
        "Rain": "дождь 🌧",
        "Drizzle": "дождь 🌧",
        "Thunderstorm": "гроза ⚡️",
        "Snow": "снег 🌨️",
        "Mist": "туман 🌫"
    }
    try:
        r = requests.get(
            f"https://api.openweathermap.org/data/2.5/weather?q={message.text}&appid={WEATHER_TOKEN}&units=metric&lang=ru"
        )
        data = r.json()

        city = data["name"]
        cur_weather = data["main"]["temp"]
        # humidity = data["main"]["humidity"]

        description = data["weather"][0]["main"]
        if description in code_to_smile:
            wd = code_to_smile[description]
        else:
            wd = "Посмотри в окно, не могу понять что там за погода...🤷"

        cur = cur_weather
        if cur <= -15:
            cur = "мороз"
        elif cur > -15 and cur <= 8:
            cur = "холодно"
        elif cur > 8 and cur <= 23:
            cur = "тепло"
        elif cur >= 23:
            cur = "жарко"

        await message.reply(f"Сейчас в городе {city} {cur_weather} C°\nНа улице {cur}, {wd}")

    except requests.exceptions.RequestException:
        await message.reply("Не удалось узнать погоду...😢\nПовтори позже")
    except KeyError:
        await message.reply("Проверь название города!🧐")

async def on_startup():
    scheduler.add_job(send_weather_notifications,
        'cron',
        minute='*',
        second=0,
        misfire_grace_time=30)
    if not scheduler.running:
        scheduler.start()
    print("Бот и планировщик успешно запущены")

async def on_shutdown():
    if scheduler.running:
        scheduler.shutdown()
    print("Планировщик остановлен")

async def main():
    init_db()

    logging.basicConfig(level=logging.INFO)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())