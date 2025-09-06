import time
import requests
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import Message

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

# === Функции поиска ===
def search_kym(query):
    url = cfg.KYM_SEARCH_URL.format(query=query)
    r = requests.get(url, headers=cfg.HEADERS, timeout=cfg.REQUEST_TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")

    first_result = soup.select_one(".entry_list a")
    if not first_result:
        return "❌ Мем не найден на KnowYourMeme."

    link = cfg.KYM_BASE_URL + first_result["href"]
    page = requests.get(link, headers=cfg.HEADERS, timeout=cfg.REQUEST_TIMEOUT)
    soup = BeautifulSoup(page.text, "html.parser")

    title = soup.select_one("h1").get_text(strip=True)
    summary = soup.select_one(".bodycopy").get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..."

    return f"📖 {title}\n{summary}\n🔗 {link}"


def search_memepedia(query):
    url = cfg.MEMEPEDIA_SEARCH_URL.format(query=query)
    r = requests.get(url, headers=cfg.HEADERS, timeout=cfg.REQUEST_TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")

    first_result = soup.select_one(".entry-title a")
    if not first_result:
        return "❌ Мем не найден на Memepedia."

    link = first_result["href"]
    page = requests.get(link, headers=cfg.HEADERS, timeout=cfg.REQUEST_TIMEOUT)
    soup = BeautifulSoup(page.text, "html.parser")

    title = soup.select_one("h1").get_text(strip=True)
    summary = soup.select_one(".entry-content").get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..."

    return f"📖 {title}\n{summary}\n🔗 {link}"


# === Хендлеры ===
@bot.on_message(filters.command("start") | button_filter(buttons.back_button))
async def start_command(_, message: Message):
    await message.reply(
        "👋 Привет! Я бот, который умеет показывать время и искать мемы.\n\n"
        f"Нажми {buttons.help_button.text} для помощи.",
        reply_markup=keyboards.main_keyboard
    )


@bot.on_message(filters.command("time") | button_filter(buttons.time_button))
async def time_command(_, message: Message):
    current_time = time.strftime("%H:%M:%S")
    await message.reply(f"⏰ Сейчас: {current_time}", reply_markup=keyboards.main_keyboard)


@bot.on_message(button_filter(buttons.meme_en_button) | filters.command("meme_en"))
async def meme_en_command(_, message: Message):
    await message.reply("✍️ Введи название мема на английском:")
    bot.set_parse_mode("Markdown")


@bot.on_message(button_filter(buttons.meme_ru_button) | filters.command("meme_ru"))
async def meme_ru_command(_, message: Message):
    await message.reply("✍️ Введи название мема на русском:")


@bot.on_message()
async def meme_search(_, message: Message):
    text = message.text.strip()

    # Если это запрос к англ. мемам
    if text.startswith("/meme_en "):
        query = text.replace("/meme_en ", "")
        result = search_kym(query)
        await message.reply(result)
    # Если это запрос к рус. мемам
    elif text.startswith("/meme_ru "):
        query = text.replace("/meme_ru ", "")
        result = search_memepedia(query)
        await message.reply(result)


# === Запуск ===
if __name__ == "__main__":
    bot.run()
