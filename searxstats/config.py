# Use system certificates instead of certifi ?
USE_SYSTEM_CERT = True

# Request count to measure response time
REQUEST_COUNT = 6

# fetcher.external_ressource: load page timeout, in seconds
BROWSER_LOAD_TIMEOUT = 20

# default headers for all HTTP requests
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:70.0) Gecko/20100101 Firefox/70.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3',
    'DNT': '1',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1'
}

# default cookies for all HTTP requests
DEFAULT_COOKIES = {
    'categories': 'general',
    'language': 'en-US',
    'locale': 'fr',
    'autocomplete': 'google',
    'image_proxy': '0',
    'method': 'GET',
    'safesearch': '0',
    'theme': 'oscar',
    'oscar-style': 'logicodev'
}
