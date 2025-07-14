import asyncio
from aiogram import Bot
from datetime import datetime, timedelta
import sqlite3
from config import WEATHER_TOKEN
import requests

async def send_scheduled_notifications(bot: Bot):
    while True:
        try:
            current_utc_time = datetime.utcnow()

            conn = sqlite3.connect('notifications.db')
            c = conn.cursor()

            # Получаем все активные уведомления
            c.execute("SELECT user_id, city, notification_time, timezone_offset FROM notifications WHERE is_active=1")
            notifications = c.fetchall()

            for notification in notifications:
                notification_id, id, city, notify_time, timezone_offset = notification

                # Рассчитываем время с учетом часового пояса
                target_time = datetime.strptime(notify_time, "%H:%M").time()
                current_time_with_offset = (current_utc_time + timedelta(hours=timezone_offset)).time()

                # Проверяем, совпадает ли текущее время (с учетом часового пояса) с временем уведомления
                if (current_time_with_offset.hour == target_time.hour and
                        current_time_with_offset.minute == target_time.minute):

                    try:
                        weather = await get_weather(city)
                        await bot.send_message(
                            chat_id=id,
                            text=f"⏰ Ежедневное уведомление для {city}:\n{weather}"
                        )
                    except Exception as e:
                        print(f"Ошибка при отправке для {id}: {e}")

            conn.close()
        except Exception as e:
            print(f"Ошибка в основном цикле: {e}")
        await asyncio.sleep(60)

async def get_weather(city: str) -> str:
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
            f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={weather_token}&units=metric&lang=ru"
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

        return f"Сейчас в городе {city} {cur_weather} C°\nНа улице {cur}, {wd}"

    except requests.exceptions.RequestException:
        return "Не удалось узнать погоду...😢\nПовтори позже"
    except KeyError:
        return "Проверь название города!🧐"
