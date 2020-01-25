import os

# Tor
TOR_HTTP_PROXY = "http://127.0.0.1:9051"
TOR_SOCKS_PROXY_HOST = "127.0.0.1"
TOR_SOCKS_PROXY_PORT = 9050

# Local cryptcheck-backend
CRYPTCHECK_BACKEND = 'http://127.0.0.1:7000'

# Request count to measure response time
REQUEST_COUNT = 6

# Fetcher.external_ressource: load page timeout, in seconds
BROWSER_LOAD_TIMEOUT = 20

# Default headers for all HTTP requests
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:70.0) Gecko/20100101 Firefox/70.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'DNT': '1',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1'
}

# Default cookies for all HTTP requests
DEFAULT_COOKIES = {
    'categories': 'general',
    'language': 'en-US',
    'locale': 'en',
    'autocomplete': 'google',
    'image_proxy': '0',
    'method': 'GET',
    'safesearch': '0',
    'theme': 'oscar',
    'oscar-style': 'logicodev'
}

# Default working directory
CACHE_DIRECTORY = '/tmp'

# File name of cache
CACHE_FILE_NAME = 'searxstats-cache.yaml'

# File name of the hashes (of static file in searx)
HASHES_FILE_NAME = 'searxstats-well-known-hashes.yaml'

# Directory where searx will be git clone
SEARX_GIT_DIRECTORY = 'searxstats-git'

# Git URL of searx (to fetch static file content hashes)
SEARX_GIT_REPOSITORY = 'https://github.com/asciimoo/searx'

# geckodriver log file name
GECKODRIVER_LOG_FILE_NAME = 'geckodriver.log'


def set_cache_directory(directory):
    global CACHE_DIRECTORY  # pylint: disable=global-statement
    CACHE_DIRECTORY = directory


def get_cache_file_name():
    global CACHE_DIRECTORY, CACHE_FILE_NAME  # pylint: disable=global-statement
    return os.path.join(CACHE_DIRECTORY, CACHE_FILE_NAME)


def get_hashes_file_name():
    global CACHE_DIRECTORY, HASHES_FILE_NAME  # pylint: disable=global-statement
    return os.path.join(CACHE_DIRECTORY, HASHES_FILE_NAME)


def get_searx_repository_directory():
    global CACHE_DIRECTORY, SEARX_GIT_DIRECTORY  # pylint: disable=global-statement
    return os.path.join(CACHE_DIRECTORY, SEARX_GIT_DIRECTORY)


def get_geckodriver_file_name():
    global CACHE_DIRECTORY, GECKODRIVER_LOG_FILE_NAME  # pylint: disable=global-statement
    return os.path.join(CACHE_DIRECTORY, 'geckodriver.log')
