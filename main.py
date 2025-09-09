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
user_state = {}
# key: user_id
# value: {"lang": "en"/"ru", "suggestions": [{"title":..., "href":...}]}

# Настройка сессии с быстрыми таймаутами
session = requests.Session()
retries = Retry(total=1, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))
session.mount('http://', HTTPAdapter(max_retries=retries))

bot = Client(
    name="my_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

# === ФУНКЦИИ ПОИСКА ===
def search_kym(query: str):
    """Поиск мема на KnowYourMeme (EN) с подсказками и точным выбором."""
    try:
        url = cfg.KYM_SEARCH_URL.format(query=query)
        r = session.get(url, headers=cfg.HEADERS, timeout=7)
        soup = BeautifulSoup(r.text, "html.parser")

        results = soup.select(".entry_list a")[:5]
        if not results:
            return "❌ Мем не найден на <b>KnowYourMeme</b>."

        # Проверка точного совпадения
        for r_item in results:
            if r_item.get_text(strip=True).lower() == query.lower():
                link = cfg.KYM_BASE_URL + r_item["href"]
                page = session.get(link, headers=cfg.HEADERS, timeout=7)
                soup_page = BeautifulSoup(page.text, "html.parser")
                title = soup_page.select_one("h1")
                summary = soup_page.select_one(".bodycopy")

                title_text = title.get_text(strip=True) if title else "Без названия"
                summary_text = summary.get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..." if summary else "Описание недоступно."

                return f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"

        # Если нет точного совпадения → список подсказок
        suggestions_list = [{"title": r.get_text(strip=True), "href": r["href"]} for r in results]
        return suggestions_list
    except Exception as e:
        return f"⚠️ Ошибка при поиске на KnowYourMeme: {e}"


def search_memepedia(query: str):
    """Поиск мема на Memepedia (RU) с безопасным извлечением текста."""
    try:
        url = cfg.MEMEPEDIA_SEARCH_URL.format(query=query)
        r = session.get(url, headers=cfg.HEADERS, timeout=7)
        soup = BeautifulSoup(r.text, "html.parser")

        results = soup.select(".entry-title a")[:5]
        if not results:
            return "❌ Мем не найден на <b>Memepedia</b>."

        for r_item in results:
            if r_item.get_text(strip=True).lower() == query.lower():
                link = r_item["href"]
                page = session.get(link, headers=cfg.HEADERS, timeout=7)
                soup_page = BeautifulSoup(page.text, "html.parser")
                title = soup_page.select_one("h1")
                summary = soup_page.select_one(".entry-content")

                title_text = title.get_text(strip=True) if title else "Без названия"
                summary_text = summary.get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..." if summary else "Описание недоступно."

                return f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"

        # если точного совпадения нет → список подсказок
        suggestions_list = [{"title": r.get_text(strip=True), "href": r["href"]} for r in results]
        return suggestions_list
    except Exception as e:
        return f"⚠️ Ошибка при поиске на Memepedia: {e}"


# === ХЕНДЛЕРЫ ===
@bot.on_message(filters.command("start") | button_filter(buttons.back_button))
async def start_command(_, message: Message):
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
    await message.reply(
        f"⏰ Сейчас: <b>{current_time}</b>",
        reply_markup=keyboards.main_keyboard,
        parse_mode=ParseMode.HTML
    )


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
    await message.reply("⏳ Ищу мем, подожди немного...")

    # Если есть предыдущие подсказки → это выбор одного из вариантов
    if "suggestions" in state:
        for s in state["suggestions"]:
            if s["title"].lower() == query.lower():
                link = cfg.KYM_BASE_URL + s["href"] if state["lang"] == "en" else s["href"]
                page = session.get(link, headers=cfg.HEADERS, timeout=7)
                soup_page = BeautifulSoup(page.text, "html.parser")
                title = soup_page.select_one("h1")
                summary = soup_page.select_one(".bodycopy" if state["lang"] == "en" else ".entry-content")

                title_text = title.get_text(strip=True) if title else "Без названия"
                summary_text = summary.get_text(strip=True)[:cfg.MAX_TEXT_LENGTH] + "..." if summary else "Описание недоступно."

                await message.reply(f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>", parse_mode=ParseMode.HTML)
                user_state.pop(uid)
                return
        await message.reply("❌ Пожалуйста, выбери один из предложенных вариантов.")
        return

    # обычный поиск
    result = search_kym(query) if state["lang"] == "en" else search_memepedia(query)

    if isinstance(result, list):  # получили список подсказок
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
