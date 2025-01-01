import time

import requests
from environs import Env
from telegram import Bot


def get_reviews(dvmn_api_url, headers, params, request_timeout):
    response = requests.get(dvmn_api_url, headers=headers, params=params, timeout=request_timeout)
    response.raise_for_status()
    return response.json()


def create_message(attempt):
    lesson_title = attempt["lesson_title"]
    lesson_url = attempt.get("lesson_url", "Нет ссылки на урок")
    is_negative = attempt["is_negative"]

    attempt_result = {
        True: "К сожалению, есть замечания. Нужно исправить!",
        False: "Работа принята! Отлично справились!",
    }

    message = (
        f"🧑‍ Преподаватель проверил работу: \n💻 {lesson_title}\n"
        f"📌 Ссылка на урок: {lesson_url}\n"
        f"{'❌ ' + attempt_result[is_negative] if is_negative else '✅ ' + attempt_result[is_negative]}"
    )
    return message


def main():
    env = Env()
    env.read_env()

    request_timeout = env.int("REQUEST_TIMEOUT")
    dvmn_api_url = "https://dvmn.org/api/long_polling/"
    dvmn_api_token = env("DVMN_API_TOKEN")
    tg_bot_api = env("TG_BOT_API")
    tg_chat_id = env("TG_CHAT_ID")

    bot = Bot(token=tg_bot_api)
    bot.send_message(chat_id=tg_chat_id, text="🤖 Бот запущен и готов к работе!")

    headers = {"Authorization": f"Token {dvmn_api_token}"}
    params = {}

    while True:
        try:
            list_of_works_data = get_reviews(dvmn_api_url, headers, params, request_timeout)

            if list_of_works_data.get("status") == "found":
                lesson_attempt = list_of_works_data["new_attempts"][0]
                message = create_message(lesson_attempt)

                bot.send_message(chat_id=tg_chat_id, text=message)

                params["timestamp"] = list_of_works_data.get("last_attempt_timestamp")

        except requests.exceptions.ReadTimeout:
            bot.send_message(
                chat_id=tg_chat_id, text=f"⚠️ Сервер не ответил за {request_timeout} секунд... Продолжаем цикл ..."
            )
            continue

        except requests.exceptions.ConnectionError:
            bot.send_message(
                chat_id=tg_chat_id, text="⚠️ Потеряно соединение с интернетом. Ожидаю восстановления..."
            )
            time.sleep(10)

        except requests.exceptions.RequestException as e:
            bot.send_message(chat_id=tg_chat_id, text=f"⚠️ Произошла ошибка: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
