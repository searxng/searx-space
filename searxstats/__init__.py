import logging
import asyncio
import uvloop

from .memoize import erase_by_name
from .ssl_utils import monkey_patch as ssl_utils_monkey_patch
from .http_utils import monkey_patch as http_utils_monkey_patch
from .instances import get_instance_urls
from .fetcher import fetch, FETCHERS


def initialize():
    ssl_utils_monkey_patch()
    http_utils_monkey_patch()
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    initialize_logging()


def initialize_logging():
    logging.basicConfig(level=logging.DEBUG)
    for logger_name in ('httpx.config', 'hpack.hpack', 'hpack.table',
                        'httpx.dispatch.connection_pool', 'httpx.dispatch.connection',
                        'httpx.dispatch.http2', 'httpx.dispatch.http11',
                        'ipwhois.rdap', 'ipwhois.ipwhois', 'ipwhois.net', 'ipwhois.asn',
                        'selenium.webdriver.remote', 'urllib3.connectionpool'):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


async def run_once(output_file: str, instance_urls: list, selected_fetcher_names: list):
    # select fetchers
    selected_fetchers = list(
        filter(lambda f: f.name in selected_fetcher_names, FETCHERS))

    # fetch instance list
    if instance_urls is None or len(instance_urls) == 0:
        instance_urls = await get_instance_urls()
    print('\n{0} instance(s)\n'.format(len(instance_urls)))

    # fetch
    searx_stats_result = await fetch(instance_urls, selected_fetchers)

    # write results
    searx_stats_result.write(output_file)


async def run_server(*args, **kwargs):
    await run_once(*args, **kwargs)
    while True:
        print('\n💤 Sleep until next run\n')
        await asyncio.sleep(24 * 3600)
        await run_once(*args, **kwargs)


def erase_memoize(fetcher_name_list: list):
    for fetcher in filter(lambda f: f.name in fetcher_name_list, FETCHERS):
        fetcher.erase_memoize()
 