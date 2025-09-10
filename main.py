from aiohttp import ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
import time
import logging
import asyncio
from typing import Dict, List, Optional, Union
import config
import config_memes as cfg
import buttons
import keyboards
from custom_filters import button_filter

# Constants
SIMILARITY_THRESHOLD = 0.2
EXACT_MATCH_THRESHOLD = 0.7
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояние пользователей
user_state: Dict[int, Dict] = {}  # key: user_id, value: {"lang": "en"/"ru", "suggestions": [...]}

bot = Client(
    name="my_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)


# === Вспомогательные функции ===
def similar(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def clean_text(block) -> str:
    """Extract and clean text from HTML element."""
    if not block:
        return ""

    # Remove links but keep their text
    for a in block.find_all("a"):
        a.replace_with(a.get_text())

    return block.get_text(strip=True)


async def fetch_html(session: ClientSession, url: str, retries: int = MAX_RETRIES) -> Optional[str]:
    """Fetch HTML content with retry logic and proper error handling."""
    for attempt in range(retries):
        try:
            async with session.get(
                    url,
                    headers=cfg.HEADERS,
                    timeout=ClientTimeout(total=REQUEST_TIMEOUT)
            ) as resp:
                if resp.status == 200:
                    return await resp.text()
                logger.warning(f"HTTP {resp.status} for {url}")

        except asyncio.TimeoutError:
            logger.warning(f"Timeout for {url} (attempt {attempt + 1}/{retries})")
        except Exception as e:
            logger.error(f"Error fetching {url}: {e} (attempt {attempt + 1}/{retries})")

        if attempt < retries - 1:
            await asyncio.sleep(1)  # Brief delay between retries

    return None


async def get_meme_details(session: ClientSession, link: str, is_kym: bool = True) -> str:
    """Extract meme details from a page."""
    page_html = await fetch_html(session, link)
    if not page_html:
        return "⚠️ Ошибка при загрузке страницы мема."

    soup_page = BeautifulSoup(page_html, "html.parser")

    # Different selectors for different sites
    content_selector = ".bodycopy" if is_kym else ".entry-content"
    content_block = soup_page.select_one(content_selector)

    summary_text = (
        clean_text(content_block)[:cfg.MAX_TEXT_LENGTH] + "..."
        if content_block else "Описание недоступно."
    )

    title = soup_page.select_one("h1")
    title_text = title.get_text(strip=True) if title else "Без названия"

    return f"📖 <b>{title_text}</b>\n{summary_text}\n\n🔗 <a href='{link}'>Открыть на сайте</a>"


# === Асинхронный поиск мемов ===
async def search_kym(query: str) -> Union[str, List[Dict[str, str]], None]:
    """Search for memes on Know Your Meme."""
    url = cfg.KYM_SEARCH_URL.format(query=query)

    async with ClientSession() as session:
        html = await fetch_html(session, url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        results = soup.select(".entry_list a")[:10]

        if not results:
            return []

        # Check for exact match
        for r_item in results:
            if r_item.get_text(strip=True).lower() == query.lower():
                link = cfg.KYM_BASE_URL + r_item["href"]
                return await get_meme_details(session, link, is_kym=True)

        # Return suggestions if no exact match
        suggestions = [
            {"title": r.get_text(strip=True), "href": r["href"]}
            for r in results
        ]

        # Filter by similarity threshold
        suggestions = [
            s for s in suggestions
            if similar(s["title"], query) >= SIMILARITY_THRESHOLD
        ]

        suggestions.sort(key=lambda s: similar(s["title"], query), reverse=True)
        return suggestions


async def search_memepedia(query: str) -> Union[str, List[Dict[str, str]]]:
    """Search for memes on Memepedia."""
    url = cfg.MEMEPEDIA_SEARCH_URL.format(query=query)

    async with ClientSession() as session:
        html = await fetch_html(session, url)
        if not html:
            return "⚠️ Не удалось подключиться к Memepedia."

        soup = BeautifulSoup(html, "html.parser")
        results = soup.select(".entry-title a")[:10]

        if not results:
            return "❌ Мем не найден на Memepedia."

        # Check for exact match
        for r_item in results:
            if r_item.get_text(strip=True).lower() == query.lower():
                link = r_item["href"]
                return await get_meme_details(session, link, is_kym=False)

        # Return suggestions if no exact match
        suggestions = [
            {"title": r.get_text(strip=True), "href": r["href"]}
            for r in results
        ]

        # Filter by similarity threshold
        suggestions = [
            s for s in suggestions
            if similar(s["title"], query) >= SIMILARITY_THRESHOLD
        ]

        suggestions.sort(key=lambda s: similar(s["title"], query), reverse=True)
        return suggestions


def clear_user_state(user_id: int) -> None:
    """Clear user state safely."""
    user_state.pop(user_id, None)


# === ХЕНДЛЕРЫ ===
@bot.on_message(filters.command(["debug", "test"]))
async def debug_command(_, message: Message):
    """Debug command to test website connectivity."""
    if not message.from_user.id in [config.ADMIN_ID] if hasattr(config, 'ADMIN_ID') else True:
        # Only allow admin or everyone if no admin is set
        pass

    await message.reply("🔍 Тестирую подключения к сайтам...")

    test_urls = [
        ("KYM Search", cfg.KYM_SEARCH_URL.format(query="test")),
        ("KYM Base", cfg.KYM_BASE_URL),
        ("Memepedia Search", cfg.MEMEPEDIA_SEARCH_URL.format(query="test"))
    ]

    results = []
    async with ClientSession() as session:
        for name, url in test_urls:
            try:
                start_time = time.time()
                html = await fetch_html(session, url)
                duration = time.time() - start_time

                if html:
                    results.append(f"✅ {name}: OK ({duration:.1f}s, {len(html)} chars)")
                else:
                    results.append(f"❌ {name}: FAILED")
            except Exception as e:
                results.append(f"❌ {name}: ERROR - {e}")

    await message.reply("\n".join(results), parse_mode=ParseMode.HTML)


@bot.on_message(filters.command("start") | button_filter(buttons.back_button))
async def start_command(_, message: Message):
    """Handle start command and back button."""
    clear_user_state(message.from_user.id)
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
    """Handle time command and button."""
    current_time = time.strftime("%H:%M:%S")
    await message.reply(
        f"⏰ Сейчас: <b>{current_time}</b>",
        reply_markup=keyboards.main_keyboard,
        parse_mode=ParseMode.HTML
    )


@bot.on_message(button_filter(buttons.meme_en_button))
async def meme_en_button(_, message: Message):
    """Handle English meme search button."""
    user_state[message.from_user.id] = {"lang": "en"}
    await message.reply("✍️ Введи название англоязычного мема:", parse_mode=ParseMode.HTML)


@bot.on_message(button_filter(buttons.meme_ru_button))
async def meme_ru_button(_, message: Message):
    """Handle Russian meme search button."""
    user_state[message.from_user.id] = {"lang": "ru"}
    await message.reply("✍️ Введи название русского мема:", parse_mode=ParseMode.HTML)


@bot.on_message(filters.command(["meme_en", "meme_ru"]))
async def meme_command(_, message: Message):
    """Handle direct meme search commands."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("❌ Пожалуйста, укажите название мема после команды.")
        return

    command, query = parts
    lang = "en" if command == "/meme_en" else "ru"
    user_state[message.from_user.id] = {"lang": lang}

    await search_and_respond(message, query.strip())


async def search_and_respond(message: Message, query: str) -> None:
    """Search for meme and send response."""
    uid = message.from_user.id
    state = user_state.get(uid, {})
    lang = state.get("lang", "en")

    logger.info(f"Searching for '{query}' in {lang} for user {uid}")

    # Show searching message
    searching_msg = await message.reply("⏳ Ищу мем...")

    try:
        if lang == "en":
            logger.info(f"Searching KYM for: {query}")
            result = await search_kym(query)
            if result is None or result == []:
                logger.info(f"KYM search failed, trying Memepedia for: {query}")
                result = await search_memepedia(query)
        else:
            logger.info(f"Searching Memepedia for: {query}")
            result = await search_memepedia(query)

        # Delete the "searching" message
        try:
            await searching_msg.delete()
        except:
            pass  # Ignore deletion errors

        if isinstance(result, list) and len(result) > 0:
            logger.info(f"Found {len(result)} suggestions for user {uid}")
            user_state[uid]["suggestions"] = result
            user_state[uid]["waiting_for_input"] = False  # No longer waiting for initial input

            suggest_text = "\n".join([f"- {s['title']}" for s in result[:5]])  # Limit suggestions
            await message.reply(
                f"🤔 Может быть, вы имели в виду:\n{suggest_text}\n\n"
                "Введите точное название из списка выше.",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_keyboard
            )
        elif isinstance(result, str):
            logger.info(f"Found exact match for user {uid}")
            await message.reply(result, parse_mode=ParseMode.HTML)
            clear_user_state(uid)
        else:
            logger.info(f"No results found for user {uid}")
            await message.reply(
                "❌ Мем не найден. Попробуйте другое название.",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_keyboard
            )
            clear_user_state(uid)

    except Exception as e:
        logger.error(f"Error in search_and_respond for user {uid}: {e}")

        # Delete the "searching" message
        try:
            await searching_msg.delete()
        except:
            pass

        await message.reply(
            "⚠️ Произошла ошибка при поиске мема. Попробуйте позже.",
            reply_markup=keyboards.main_keyboard
        )
        clear_user_state(uid)


# === ОБРАБОТКА ВВОДА МЕМА ===
@bot.on_message(filters.text & ~filters.command(["start", "time", "meme_en", "meme_ru"]))
async def handle_meme_text(_, message: Message):
    """Handle meme text input."""
    uid = message.from_user.id
    if uid not in user_state:
        return

    state = user_state[uid]
    query = message.text.strip()

    # If there are suggestions, look for close matches
    if "suggestions" in state:
        best_match = None
        best_similarity = 0

        for s in state["suggestions"]:
            similarity = similar(s["title"], query)
            if similarity > best_similarity and similarity > EXACT_MATCH_THRESHOLD:
                best_match = s
                best_similarity = similarity

        if best_match:
            is_kym = state["lang"] == "en"
            link = (cfg.KYM_BASE_URL + best_match["href"]) if is_kym else best_match["href"]

            async with ClientSession() as session:
                result = await get_meme_details(session, link, is_kym)
                await message.reply(result, parse_mode=ParseMode.HTML)
                clear_user_state(uid)
                return

        # If no close match found
        await message.reply(
            "❌ Пожалуйста, выберите один из предложенных вариантов или начните новый поиск.",
            reply_markup=keyboards.main_keyboard
        )
        return

    # New search
    await search_and_respond(message, query)


# === ЗАПУСК ===
if __name__ == "__main__":
    logger.info("Бот запускается...")
    bot.run()