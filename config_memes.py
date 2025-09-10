# config_memes.py
# Настройки для парсинга мемов

KYM_BASE_URL = "https://knowyourmeme.com"
MEMEPEDIA_BASE_URL = "https://memepedia.ru"

KYM_SEARCH_URL = KYM_BASE_URL + "/search?q={query}"
MEMEPEDIA_SEARCH_URL = MEMEPEDIA_BASE_URL + "/?s={query}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0 Safari/537.36"
}

REQUEST_TIMEOUT = 10
MAX_TEXT_LENGTH = 500
