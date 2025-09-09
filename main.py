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

# Состояние пользователей
user_state = {}  # key: user_id, value: {"lang": "en"/"ru", "suggestions": [...]}

# Настройка сессии с повторными попытками
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500,502,503,504])
session.mount('https://', HTTPAdapter(max_retries=retries))
session.mount('http://', HTTPAdapter(max_retries=retries))

# User-Agent
cfg.HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/117.0 Safari/537.36"
}

bot = Client(
    name="my_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

# === ПОИСК МЕМОВ ===
def search_kym(query: str):
    """Поиск мема на KYM с подсказками и таймаутом."""
    try:
        url = cfg.KYM_SEARCH_URL.format(query=query)
        time.sleep(1)
        r = session.get(url, headers=cfg.HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        results = soup.select(".entry_list a")[:5]

        if not results:
            return []  # будем использовать как подсказку для Memepedia

        # точное совпадение
        for r_item in results:
            if r_item.get_text(strip=True).lower() == query.lower():
                link = cfg.KYM_BASE_URL + r_item["href"]
                page = session.get(link, headers=cfg.HEADERS, timeout=20)
                soup_page = BeautifulSoup(page.text, "html.parser")
                title = soup_page.select_one("h1")
                summary = soup_page.select_one(".bodycopy")

                title_text = title.get_text(strip=True) if title else "Без названия"
                summary_text = summary.get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..." if summary else "Описание недоступно."
                return f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"

        # если нет точного совпадения → список подсказок
        suggestions = [{"title": r.get_text(strip=True), "href": r["href"]} for r in results]
        return suggestions
    except Exception:
        return None  # KYM недоступен

def search_memepedia(query: str, lang="ru"):
    """Поиск мема на Memepedia с подсказками."""
    try:
        url = cfg.MEMEPEDIA_SEARCH_URL.format(query=query)
        time.sleep(1)
        r = session.get(url, headers=cfg.HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        results = soup.select(".entry-title a")[:5]

        if not results:
            return "❌ Мем не найден на Memepedia."

        # точное совпадение
        for r_item in results:
            if r_item.get_text(strip=True).lower() == query.lower():
                link = r_item["href"]
                page = session.get(link, headers=cfg.HEADERS, timeout=20)
                soup_page = BeautifulSoup(page.text, "html.parser")
                title = soup_page.select_one("h1")
                summary = soup_page.select_one(".entry-content")

                title_text = title.get_text(strip=True) if title else "Без названия"
                summary_text = summary.get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..." if summary else "Описание недоступно."
                return f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"

        # подсказки
        suggestions = [{"title": r.get_text(strip=True), "href": r["href"]} for r in results]
        return suggestions
    except Exception:
        return "⚠️ Не удалось подключиться к Memepedia."

# === ХЕНДЛЕРЫ ===
@bot.on_message(filters.command("start") | button_filter(buttons.back_button))
async def start_command(_, message: Message):
    await message.reply(
        "👋 Привет! Я бот для поиска мемов.\n\n"
        "Доступные команды:\n"
        "<b>/time</b> – текущее время ⏰\n"
        "<b>/meme_en &lt;название&gt;</b> – английский мем 🇺🇸\n"
        "<b>/meme_ru &lt;название&gt;</b> – русский мем 🇷🇺\n",
        reply_markup=keyboards.main_keyboard,
        parse_mode=ParseMode.HTML
    )

@bot.on_message(filters.command("time") | button_filter(buttons.time_button))
async def time_command(_, message: Message):
    current_time = time.strftime("%H:%M:%S")
    await message.reply(f"⏰ Сейчас: <b>{current_time}</b>", reply_markup=keyboards.main_keyboard, parse_mode=ParseMode.HTML)

# === КНОПКИ МЕМОВ ===
@bot.on_message(button_filter(buttons.meme_en_button))
async def meme_en_button(_, message: Message):
    user_state[message.from_user.id] = {"lang": "en"}
    await message.reply("✍️ Введи название англоязычного мема:", parse_mode=ParseMode.HTML)

@bot.on_message(button_filter(buttons.meme_ru_button))
async def meme_ru_button(_, message: Message):
    user_state[message.from_user.id] = {"lang": "ru"}
    await message.reply("✍️ Введи название русского мема:", parse_mode=ParseMode.HTML)

# === ОБРАБОТКА ВВОДА МЕМА ===
@bot.on_message()
async def handle_meme_text(_, message: Message):
    uid = message.from_user.id
    if uid not in user_state:
        return

    state = user_state[uid]
    query = message.text.strip()
    await message.reply("⏳ Ищу мем...")

    if "suggestions" in state:
        for s in state["suggestions"]:
            if s["title"].lower() == query.lower():
                link = cfg.KYM_BASE_URL + s["href"] if state["lang"] == "en" else s["href"]
                page = session.get(link, headers=cfg.HEADERS, timeout=20)
                soup_page = BeautifulSoup(page.text, "html.parser")
                title = soup_page.select_one("h1")
                summary = soup_page.select_one(".bodycopy" if state["lang"] == "en" else ".entry-content")

                title_text = title.get_text(strip=True) if title else "Без названия"
                summary_text = summary.get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..." if summary else "Описание недоступно."
                await message.reply(f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>", parse_mode=ParseMode.HTML)
                user_state.pop(uid)
                return
        await message.reply("❌ Пожалуйста, выберите один из предложенных вариантов.")
        return

    # Поиск английских мемов сначала на KYM
    if state["lang"] == "en":
        result = search_kym(query)
        if result is None or result == []:  # KYM не ответил или нет совпадений → Memepedia EN
            result = search_memepedia(query, lang="en")
    else:
        result = search_memepedia(query, lang="ru")

    if isinstance(result, list):
        user_state[uid]["suggestions"] = result
        suggest_text = "\n".join([f"- {s['title']}" for s in result])
        await message.reply(f"🤔 Может быть, вы имели в виду:\n{suggest_text}", parse_mode=ParseMode.HTML)
    else:
        await message.reply(result, parse_mode=ParseMode.HTML)
        user_state.pop(uid)

# === ЗАПУСК ===
if __name__ == "__main__":
    print("[LOG] Бот запускается...")
    bot.run()
