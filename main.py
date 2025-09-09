import asyncio
from aiohttp import ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

import config
import config_memes as cfg
import buttons
import keyboards
from custom_filters import button_filter

# Состояние пользователей
user_state = {}  # key: user_id, value: {"lang": "en"/"ru", "suggestions": [...]}

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
    if not block:
        return ""
    for a in block.find_all("a"):
        a.replace_with(a.get_text())
    return block.get_text(strip=True)

async def fetch_html(session, url):
    try:
        async with session.get(url, headers=cfg.HEADERS, timeout=ClientTimeout(total=10)) as resp:
            return await resp.text()
    except:
        return None

# === Асинхронный поиск мемов ===
async def search_kym(query: str):
    url = cfg.KYM_SEARCH_URL.format(query=query)
    async with ClientSession() as session:
        html = await fetch_html(session, url)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        results = soup.select(".entry_list a")[:10]
        if not results:
            return []

        for r_item in results:
            if r_item.get_text(strip=True).lower() == query.lower():
                link = cfg.KYM_BASE_URL + r_item["href"]
                page_html = await fetch_html(session, link)
                if not page_html:
                    return "⚠️ Ошибка при загрузке страницы мема на KYM."
                soup_page = BeautifulSoup(page_html, "html.parser")
                summary_block = soup_page.select_one(".bodycopy")
                summary_text = clean_text(summary_block)[:cfg.MAX_TEXT_LENGTH] + "..." if summary_block else "Описание недоступно."
                title = soup_page.select_one("h1")
                title_text = title.get_text(strip=True) if title else "Без названия"
                return f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"

        threshold = 0.2
        suggestions = [{"title": r.get_text(strip=True), "href": r["href"]} for r in results]
        suggestions = [s for s in suggestions if similar(s["title"], query) >= threshold]
        suggestions.sort(key=lambda s: similar(s["title"], query), reverse=True)
        return suggestions

async def search_memepedia(query: str):
    url = cfg.MEMEPEDIA_SEARCH_URL.format(query=query)
    async with ClientSession() as session:
        html = await fetch_html(session, url)
        if not html:
            return "⚠️ Не удалось подключиться к Memepedia."
        soup = BeautifulSoup(html, "html.parser")
        results = soup.select(".entry-title a")[:10]
        if not results:
            return "❌ Мем не найден на Memepedia."

        for r_item in results:
            if r_item.get_text(strip=True).lower() == query.lower():
                link = r_item["href"]
                page_html = await fetch_html(session, link)
                if not page_html:
                    return "⚠️ Ошибка при загрузке страницы мема на Memepedia."
                soup_page = BeautifulSoup(page_html, "html.parser")
                content_block = soup_page.select_one(".entry-content")
                summary_text = clean_text(content_block)[:cfg.MAX_TEXT_LENGTH] + "..." if content_block else "Описание недоступно."
                title = soup_page.select_one("h1")
                title_text = title.get_text(strip=True) if title else "Без названия"
                return f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"

        threshold = 0.2
        suggestions = [{"title": r.get_text(strip=True), "href": r["href"]} for r in results]
        suggestions = [s for s in suggestions if similar(s["title"], query) >= threshold]
        suggestions.sort(key=lambda s: similar(s["title"], query), reverse=True)
        return suggestions

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

    # Если есть предложения, ищем ближайшее совпадение
    if "suggestions" in state:
        for s in state["suggestions"]:
            if similar(s["title"], query) > 0.7:
                link = cfg.KYM_BASE_URL + s["href"] if state["lang"] == "en" else s["href"]
                async with ClientSession() as session:
                    page_html = await fetch_html(session, link)
                soup_page = BeautifulSoup(page_html, "html.parser")
                content_block = soup_page.select_one(".bodycopy" if state["lang"] == "en" else ".entry-content")
                summary_text = clean_text(content_block)[:cfg.MAX_TEXT_LENGTH] + "..." if content_block else "Описание недоступно."
                title = soup_page.select_one("h1")
                title_text = title.get_text(strip=True) if title else "Без названия"
                await message.reply(f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>", parse_mode=ParseMode.HTML)
                user_state.pop(uid)
                return

        # Если ни одно не подошло
        await message.reply("❌ Пожалуйста, выберите один из предложенных вариантов.")
        return

    # Поиск по новому запросу
    if state["lang"] == "en":
        result = await search_kym(query)
        if result is None or result == []:
            result = await search_memepedia(query)
    else:
        result = await search_memepedia(query)

    if isinstance(result, list) and len(result) > 0:
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
