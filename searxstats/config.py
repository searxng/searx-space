import os
import hashlib

# Tor
TOR_SOCKS_PROXY_HOST = "127.0.0.1"
TOR_SOCKS_PROXY_PORT = 9050

# Local cryptcheck-backend
CRYPTCHECK_BACKEND = 'http://127.0.0.1:7000'

# Fetcher.external_ressource: load page timeout, in seconds
BROWSER_LOAD_TIMEOUT = 20

# Default headers for all HTTP requests
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0',
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

# Database URL
DATABASE_URL = 'sqlite:////tmp/searxstats.db'

# Directory where searx will be git clone
SEARX_GIT_DIRECTORY = 'searxstats-git'

SEARXINSTANCES_GIT_DIRECTORY = 'searxinstances-git'

# Git URL of searx (to fetch static file content hashes)
SEARX_GIT_REPOSITORY = 'https://github.com/searx/searx'
SEARXNG_GIT_REPOSITORY = 'https://github.com/searxng/searxng'

SEARXINSTANCES_GIT_REPOSITORY = 'https://github.com/searxng/searx-instances'

# geckodriver log file name
GECKODRIVER_LOG_FILE_NAME = 'geckodriver.log'

# mmdb
MMDB_FILENAME = os.environ.get("MMDB_FILENAME")

# debian
DEBIAN_GIT_URL = 'https://salsa.debian.org/debian/searx'
DEBIAN_SOURCE_PACKAGE_NAMES = [
    'searx', 'twitter-bootstrap3', 'jquery', 'leaflet', 'requirejs', 'typeahead.js']

#
FORKS = [
    'https://github.com/searx/searx',
    'https://github.com/searxng/searxng',
    'https://salsa.debian.org/debian/searx',
    'https://gitlab.e.foundation/e/cloud/my-spot',
]


def set_cache_directory(directory):
    global CACHE_DIRECTORY  # pylint: disable=global-statement
    CACHE_DIRECTORY = directory


def set_database_url(database_url):
    global DATABASE_URL  # pylint: disable=global-statement
    DATABASE_URL = database_url


def get_database_url():
    return DATABASE_URL


def get_cache_file_name():
    global CACHE_DIRECTORY, CACHE_FILE_NAME  # pylint: disable=global-statement
    return os.path.join(CACHE_DIRECTORY, CACHE_FILE_NAME)


def get_git_repository_path(url: str) -> str:
    global CACHE_DIRECTORY  # pylint: disable=global-statement
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    name = "git-" + url_hash
    return os.path.join(os.path.join(CACHE_DIRECTORY, 'git'), name)


def get_geckodriver_file_name():
    global CACHE_DIRECTORY, GECKODRIVER_LOG_FILE_NAME  # pylint: disable=global-statement
    return os.path.join(CACHE_DIRECTORY, 'geckodriver.log')
