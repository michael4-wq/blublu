import time
import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from difflib import SequenceMatcher

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

# === Вспомогательные функции ===
def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def clean_text(block):
    """Удаляем все ссылки и оставляем только текст"""
    for a in block.find_all("a"):
        a.replace_with(a.get_text())
    return block.get_text(strip=True)

# === ПОИСК МЕМОВ ===
def search_kym(query: str):
    try:
        url = cfg.KYM_SEARCH_URL.format(query=query)
        time.sleep(1)
        r = session.get(url, headers=cfg.HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        results = soup.select(".entry_list a")[:10]

        if not results:
            return []

        # точное совпадение
        for r_item in results:
            if r_item.get_text(strip=True).lower() == query.lower():
                link = cfg.KYM_BASE_URL + r_item["href"]
                page = session.get(link, headers=cfg.HEADERS, timeout=20)
                soup_page = BeautifulSoup(page.text, "html.parser")
                summary_block = soup_page.select_one(".bodycopy")
                summary_text = clean_text(summary_block)[:cfg.MAX_TEXT_LENGTH] + "..." if summary_block else "Описание недоступно."
                title = soup_page.select_one("h1")
                title_text = title.get_text(strip=True) if title else "Без названия"
                return f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"

        # подсказки с фильтром по схожести
        suggestions = [{"title": r.get_text(strip=True), "href": r["href"]} for r in results]
        suggestions = [s for s in suggestions if similar(s["title"], query) >= 0.4]
        suggestions.sort(key=lambda s: similar(s["title"], query), reverse=True)
        return suggestions

    except Exception:
        return None

def search_memepedia(query: str, lang="ru"):
    try:
        url = cfg.MEMEPEDIA_SEARCH_URL.format(query=query)
        time.sleep(1)
        r = session.get(url, headers=cfg.HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        results = soup.select(".entry-title a")[:10]

        if not results:
            return "❌ Мем не найден на Memepedia."

        # точное совпадение
        for r_item in results:
            if r_item.get_text(strip=True).lower() == query.lower():
                link = r_item["href"]
                page = session.get(link, headers=cfg.HEADERS, timeout=20)
                soup_page = BeautifulSoup(page.text, "html.parser")
                content_block = soup_page.select_one(".entry-content")
                summary_text = clean_text(content_block)[:cfg.MAX_TEXT_LENGTH] + "..." if content_block else "Описание недоступно."
                title = soup_page.select_one("h1")
                title_text = title.get_text(strip=True) if title else "Без названия"
                return f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"

        # подсказки
        suggestions = [{"title": r.get_text(strip=True), "href": r["href"]} for r in results]
        suggestions = [s for s in suggestions if similar(s["title"], query) >= 0.4]
        suggestions.sort(key=lambda s: similar(s["title"], query), reverse=True)
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
                content_block = soup_page.select_one(".bodycopy" if state["lang"] == "en" else ".entry-content")
                summary_text = clean_text(content_block)[:cfg.MAX_TEXT_LENGTH] + "..." if content_block else "Описание недоступно."
                title = soup_page.select_one("h1")
                title_text = title.get_text(strip=True) if title else "Без названия"

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
