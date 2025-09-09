import time
import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

import config
import config_memes as cfg
import buttons
import keyboards
from custom_filters import button_filter

# Словарь для хранения состояния пользователей
user_state = {}  # key: user_id, value: "en" или "ru"

# Настройка сессии с повторными попытками
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))
session.mount('http://', HTTPAdapter(max_retries=retries))

bot = Client(
    name="my_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)


# === ФУНКЦИИ ПОИСКА ===
def search_kym(query: str) -> str:
    """Поиск мема на KnowYourMeme (EN) с повторными попытками."""
    try:
        url = cfg.KYM_SEARCH_URL.format(query=query)
        r = session.get(url, headers=cfg.HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")

        first_result = soup.select_one(".entry_list a")
        if not first_result:
            return "❌ Мем не найден на <b>KnowYourMeme</b>."

        link = cfg.KYM_BASE_URL + first_result["href"]
        page = session.get(link, headers=cfg.HEADERS, timeout=30)
        soup = BeautifulSoup(page.text, "html.parser")

        title = soup.select_one("h1")
        summary = soup.select_one(".bodycopy")

        if not title or not summary:
            return "⚠️ Не удалось извлечь данные с KnowYourMeme."

        text = summary.get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..."

        return f"📖 <b>{title.get_text(strip=True)}</b>\n{text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"
    except Exception as e:
        return f"⚠️ Ошибка при поиске на KnowYourMeme: {e}"


def search_memepedia(query: str) -> str:
    """Поиск мема на Memepedia (RU) с повторными попытками."""
    try:
        url = cfg.MEMEPEDIA_SEARCH_URL.format(query=query)
        r = session.get(url, headers=cfg.HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")

        first_result = soup.select_one(".entry-title a")
        if not first_result:
            return "❌ Мем не найден на <b>Memepedia</b>."

        link = first_result["href"]
        page = session.get(link, headers=cfg.HEADERS, timeout=30)
        soup = BeautifulSoup(page.text, "html.parser")

        title = soup.select_one("h1")
        summary = soup.select_one(".entry-content")

        if not title or not summary:
            return "⚠️ Не удалось извлечь данные с Memepedia."

        text = summary.get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..."

        return f"📖 <b>{title.get_text(strip=True)}</b>\n{text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"
    except Exception as e:
        return f"⚠️ Ошибка при поиске на Memepedia: {e}"


# === ХЕНДЛЕРЫ ===
@bot.on_message(filters.command("start") | button_filter(buttons.back_button))
async def start_command(_, message: Message):
    print(f"[LOG] Пользователь {message.from_user.id} написал /start")
    await message.reply(
        "👋 Привет! Я бот, который умеет показывать время и искать мемы.\n\n"
        "Доступные команды:\n"
        "<b>/time</b> – текущее время ⏰\n"
        "<b>/meme_en &lt;название&gt;</b> – поиск англоязычного мема 🇺🇸\n"
        "<b>/meme_ru &lt;название&gt;</b> – поиск русского мема 🇷🇺\n",
        reply_markup=keyboards.main_keyboard,
        parse_mode=ParseMode.HTML
    )


@bot.on_message(filters.command("time") | button_filter(buttons.time_button))
async def time_command(_, message: Message):
    current_time = time.strftime("%H:%M:%S")
    print(f"[LOG] Пользователь {message.from_user.id} запросил время")
    await message.reply(
        f"⏰ Сейчас: <b>{current_time}</b>",
        reply_markup=keyboards.main_keyboard,
        parse_mode=ParseMode.HTML
    )


# === КНОПКИ МЕМОВ ===
@bot.on_message(button_filter(buttons.meme_en_button))
async def meme_en_button(_, message: Message):
    user_state[message.from_user.id] = "en"
    await message.reply("✍️ Введи название англоязычного мема:", parse_mode=ParseMode.HTML)


@bot.on_message(button_filter(buttons.meme_ru_button))
async def meme_ru_button(_, message: Message):
    user_state[message.from_user.id] = "ru"
    await message.reply("✍️ Введи название русского мема:", parse_mode=ParseMode.HTML)


# === ОБРАБОТКА ВВОДА МЕМА ===
@bot.on_message()
async def handle_meme_text(_, message: Message):
    uid = message.from_user.id
    if uid not in user_state:
        return

    query = message.text.strip()
    await message.reply("⏳ Ищу мем, подожди немного...")

    if user_state[uid] == "en":
        result = search_kym(query)
    else:
        result = search_memepedia(query)

    await message.reply(result, parse_mode=ParseMode.HTML)
    user_state.pop(uid)


# === ЗАПУСК ===
if __name__ == "__main__":
    print("[LOG] Бот запускается...")
    bot.run()
