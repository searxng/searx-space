import asyncio
import concurrent.futures

from searxstats.common.utils import wait_get_results
from searxstats.model import SearxStatisticsResult, Fetcher

from . import basic
from . import external_ressources
from . import network
from . import selfreport
from . import mozillaobs
from . import timing


__all__ = ['FETCHERS', 'fetch']


TASK_THREADPOOL = concurrent.futures.ThreadPoolExecutor(max_workers=8)
FETCHERS = [
    Fetcher(basic,
            'basic',
            'Fetch basic information 🍰👽❌',
            'basic',
            True),
    Fetcher(external_ressources,
            'html-grade',
            'Load page with a browser and check the used external ressources 🔗',
            'browser'),
    Fetcher(network,
            'network',
            'Fetch whois information 🌏',
            'other'),
    Fetcher(selfreport,
            'self-report',
            'Fetch the /status and /config URLs 💡',
            'other'),
    Fetcher(mozillaobs,
            'csp-grade',
            'Check the CSP grade 📄',
            'other'),
    Fetcher(timing,
            'timing',
            'Test the response time 🔎🐘🔍🏁❌',
            'timing'),
]


async def initialize(selected_fetchers: list):
    loop = asyncio.get_event_loop()
    for fetcher in selected_fetchers:
        await fetcher.create_initialize_task(loop, TASK_THREADPOOL)


async def fetch(searx_stats_result: SearxStatisticsResult, selected_fetchers: list):
    # fetch using the selected fetchers
    loop = asyncio.get_event_loop()

    # create a task list from the selected fetchers
    tasks_for_group = []
    current_group_name = None
    for fetcher in FETCHERS:
        if fetcher in selected_fetchers or fetcher.mandatory:
            # if fetcher is from a different group name, wait for the current tasks
            if current_group_name != fetcher.group_name:
                await wait_get_results(*tasks_for_group)
                tasks_for_group = []

            # add to the list
            current_group_name = fetcher.group_name
            task = fetcher.create_fetch_task(loop, TASK_THREADPOOL, searx_stats_result)
            tasks_for_group.append(task)

    # execute the last task list
    await wait_get_results(*tasks_for_group)
