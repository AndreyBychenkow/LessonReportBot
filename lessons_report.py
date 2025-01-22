import time
import requests
import logging
import traceback
from environs import Env
from telegram import Bot

logging.basicConfig(
	filename='bot.log',
	level=logging.INFO,
	format='%(asctime)s - %(levelname)s - %(message)s'
)


class TelegramLogHandler(logging.Handler):
	def __init__(self, bot_token, chat_id):
		super().__init__()
		self.bot = Bot(token=bot_token)
		self.chat_id = chat_id

	def emit(self, record):
		log_entry = self.format(record)
		try:
			self.bot.send_message(chat_id=self.chat_id, text=log_entry)
		except Exception as e:
			logging.error(f"Ошибка отправки лога в Telegram: {e}")


def get_reviews(dvmn_api_url, headers, params, timeout, retries=3):
	for attempt in range(retries):
		try:
			response = requests.get(dvmn_api_url, headers=headers, params=params, timeout=timeout)
			response.raise_for_status()
			return response.json()
		except requests.exceptions.ReadTimeout:
			if attempt < retries - 1:
				time.sleep(2 ** attempt)
				continue
			else:
				raise
		except requests.exceptions.RequestException as e:
			raise Exception(f"Ошибка запроса: {e}")


def create_message(attempt):
	lesson_title = attempt["lesson_title"]
	lesson_url = attempt.get("lesson_url", "Нет ссылки на урок")
	is_negative = attempt["is_negative"]

	attempt_result = {
		True: "К сожалению, есть замечания. Нужно исправить!",
		False: "Работа принята! Отлично справились!",
	}

	message = (
		f"🧑‍ Преподаватель проверил работу:\n💻 {lesson_title}\n"
		f"📌 Ссылка на урок: {lesson_url}\n"
		f"{'❌ ' + attempt_result[is_negative] if is_negative else '✅ ' + attempt_result[is_negative]}"
	)
	return message


def split_message(text, max_length=4096):
	return [text[i:i + max_length] for i in range(0, len(text), max_length)]


def main():
	env = Env()
	env.read_env()

	config = {
		"request_timeout": env.int("REQUEST_TIMEOUT", 90),
		"dvmn_api_token": env("DVMN_API_TOKEN"),
		"tg_bot_api": env("TG_BOT_API"),
		"tg_chat_id": env("TG_CHAT_ID")
	}

	telegram_handler = TelegramLogHandler(config["tg_bot_api"], config["tg_chat_id"])
	logging.getLogger().addHandler(telegram_handler)

	bot = Bot(token=config["tg_bot_api"])
	bot.send_message(chat_id=config["tg_chat_id"], text="🤖 Запускаем...")
	logging.info("Запуск бота прошел успешно! Начинаю ожидать ответа от DVMN.")

	headers = {"Authorization": f"Token {config['dvmn_api_token']}"}
	params = {}

	while True:
		try:
			list_of_works_data = get_reviews(
				"https://dvmn.org/api/long_polling/", headers, params, config["request_timeout"]
			)

			if list_of_works_data.get("status") == "found":
				lesson_attempts = list_of_works_data["new_attempts"]

				for attempt in lesson_attempts:
					message = create_message(attempt)

					for chunk in split_message(message):
						bot.send_message(chat_id=config["tg_chat_id"], text=chunk)

				params["timestamp"] = list_of_works_data.get("last_attempt_timestamp", params.get("timestamp"))

		except requests.exceptions.ReadTimeout:
			logging.warning("Превышено время ожидания ответа от API DVMN")
			bot.send_message(chat_id=config["tg_chat_id"],
							 text="⚠️ Превышено время ожидания ответа от API DVMN. Повторяю запрос...")
		except Exception as e:
			error_message = f"⚠️ Произошла ошибка:\n{traceback.format_exc()}"
			for chunk in split_message(error_message):
				bot.send_message(chat_id=config["tg_chat_id"], text=chunk)
			logging.error(f"Произошла ошибка: {e}")
			time.sleep(10)


if __name__ == "__main__":
	main()
