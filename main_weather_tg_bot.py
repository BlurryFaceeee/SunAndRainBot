import requests
from pprint import pprint

def get_weather(city, weather_token):
    try:
        r = requests.get(
            f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={weather_token}&units=metric&lang=ru"
        )
        data = r.json()
        pprint(data)

        city = data["name"]
        cur_weather = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        description = data["weather"][0]["description"]


        print(f"Погода в городе {city}\nТемпература: {cur_weather} C°\nСостояние: {description}\nВлажность: {humidity}%")

    except Exception as ex:
        print(ex)
        print("Проверьте название города!")
