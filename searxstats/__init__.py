import logging
import asyncio

from .fetcher import fetch, initialize as initialize_fetcher, FETCHERS
from .database import initialize_database
from .searx_instances import get_searx_stats_result_from_repository, get_searx_stats_result_from_list


async def initialize():
    initialize_logging()
    initialize_database()


def initialize_logging():
    logging.basicConfig(level=logging.DEBUG)
    for logger_name in ('httpx', 'httpcore', 'hpack.hpack', 'hpack.table',
                        'ipwhois.rdap', 'ipwhois.ipwhois', 'ipwhois.net', 'ipwhois.asn',
                        'selenium.webdriver.remote', 'selenium.webdriver.common',
                        'urllib3.connectionpool',
                        'git.cmd', 'git.repo', 'git.util'):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


async def run_once(output_file: str, private: bool, instance_urls: list, selected_fetcher_names: list):
    # select fetchers
    selected_fetchers = list(
        filter(lambda f: f.name in selected_fetcher_names, FETCHERS))

    # initialize fetchers
    await initialize_fetcher(selected_fetchers)

    # fetch instance list
    if not private and (instance_urls is None or len(instance_urls) == 0):
        searx_stats_result = await get_searx_stats_result_from_repository()
    else:
        searx_stats_result = await get_searx_stats_result_from_list(instance_urls, private)

    # output
    print('\n{0} instance(s)\n'.format(len(searx_stats_result.instances.keys())))

    # fetch
    await fetch(searx_stats_result, selected_fetchers)

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
