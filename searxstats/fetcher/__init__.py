import asyncio
import concurrent.futures

from searxstats.common.utils import wait_get_results
from searxstats.model import SearxStatisticsResult, Fetcher

from . import basic
from . import external_ressources
from . import network
from . import selfreport
from . import cryptcheck_backend
from . import mozillaobs
from . import timing


__all__ = ['FETCHERS', 'fetch']


TASK_THREADPOOL = concurrent.futures.ThreadPoolExecutor(max_workers=8)
FETCHERS = [
    Fetcher(network,
            'network',
            'Fetch whois information 🌏'),
    Fetcher(external_ressources,
            'html-grade',
            'Load page with a browser and check the used external ressources 🔗'),
    Fetcher(selfreport,
            'self-report',
            'Fetch the /status and /config URLs 💡'),
    Fetcher(timing,
            'timing',
            'Test the response time 🏠🔎🔍🏁❌'),
    Fetcher(cryptcheck_backend,
            'https-grade',
            'Check the HTTPS / TLS grade 🔒'),
    Fetcher(mozillaobs,
            'csp-grade',
            'Check the CSP grade 📄'),
]


async def initialize(selected_fetchers: list):
    loop = asyncio.get_event_loop()
    for fetcher in selected_fetchers:
        await fetcher.create_initialize_task(loop, TASK_THREADPOOL)


async def fetch_using_fetchers(searx_stats_result: SearxStatisticsResult, selected_fetchers: list):
    loop = asyncio.get_event_loop()

    # create a task list from the selected fetchers
    tasks = []
    for fetcher in selected_fetchers:
        task = fetcher.create_fetch_task(loop, TASK_THREADPOOL, searx_stats_result)
        tasks.append(task)

    # check if there is a least one task
    await wait_get_results(*tasks)


async def fetch(instance_urls: list, selected_fetchers: list) -> SearxStatisticsResult:
    searx_stats_result = SearxStatisticsResult()

    # initial fetch
    await basic.fetch_from_urls(searx_stats_result, instance_urls)

    # fetch using the selected fetchers
    await fetch_using_fetchers(searx_stats_result, selected_fetchers)

    return searx_stats_result
