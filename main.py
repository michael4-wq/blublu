import time
import requests
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode  # <-- исправлено здесь

import config
import config_memes as cfg
import buttons
import keyboards
from custom_filters import button_filter


bot = Client(
    name="my_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)


# === ФУНКЦИИ ПОИСКА ===
def search_kym(query: str) -> str:
    """Поиск мема на KnowYourMeme (EN)."""
    try:
        url = cfg.KYM_SEARCH_URL.format(query=query)
        r = requests.get(url, headers=cfg.HEADERS, timeout=cfg.REQUEST_TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")

        first_result = soup.select_one(".entry_list a")
        if not first_result:
            return "❌ Мем не найден на <b>KnowYourMeme</b>."

        link = cfg.KYM_BASE_URL + first_result["href"]
        page = requests.get(link, headers=cfg.HEADERS, timeout=cfg.REQUEST_TIMEOUT)
        soup = BeautifulSoup(page.text, "html.parser")

        title = soup.select_one("h1").get_text(strip=True)
        summary = soup.select_one(".bodycopy").get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..."

        return f"📖 <b>{title}</b>\n{summary}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"
    except Exception as e:
        return f"⚠️ Ошибка при поиске на KnowYourMeme: {e}"


def search_memepedia(query: str) -> str:
    """Поиск мема на Memepedia (RU)."""
    try:
        url = cfg.MEMEPEDIA_SEARCH_URL.format(query=query)
        r = requests.get(url, headers=cfg.HEADERS, timeout=cfg.REQUEST_TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")

        first_result = soup.select_one(".entry-title a")
        if not first_result:
            return "❌ Мем не найден на <b>Memepedia</b>."

        link = first_result["href"]
        page = requests.get(link, headers=cfg.HEADERS, timeout=cfg.REQUEST_TIMEOUT)
        soup = BeautifulSoup(page.text, "html.parser")

        title = soup.select_one("h1").get_text(strip=True)
        summary = soup.select_one(".entry-content").get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..."

        return f"📖 <b>{title}</b>\n{summary}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"
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


@bot.on_message(filters.command("meme_en"))
async def meme_en_command(_, message: Message):
    query = " ".join(message.text.split()[1:])
    if not query:
        await message.reply(
            "✍️ Напиши название мема: <b>/meme_en rickroll</b>",
            parse_mode=ParseMode.HTML
        )
        return
    print(f"[LOG] Поиск англоязычного мема: {query}")
    result = search_kym(query)
    await message.reply(result, parse_mode=ParseMode.HTML)


@bot.on_message(filters.command("meme_ru"))
async def meme_ru_command(_, message: Message):
    query = " ".join(message.text.split()[1:])
    if not query:
        await message.reply(
            "✍️ Напиши название мема: <b>/meme_ru жабка</b>",
            parse_mode=ParseMode.HTML
        )
        return
    print(f"[LOG] Поиск русского мема: {query}")
    result = search_memepedia(query)
    await message.reply(result, parse_mode=ParseMode.HTML)


# === ЗАПУСК ===
if __name__ == "__main__":
    print("[LOG] Бот запускается...")
    bot.run()

