import asyncio
import sys

from searxstats.model import SearxStatisticsResult, Fetcher
from .basic import fetch_from_urls
from .external_ressources import fetch as fetch_external_ressources
from .network import fetch as fetch_network
from .selfreport import fetch as fetch_selfreport
from .cryptcheck import fetch as fetch_cryptcheck
from .mozillaobs import fetch as fetch_mozillaobs
from .timing import fetch as fetch_timing


__all__ = ['FETCHERS', 'fetch']


FETCHERS = [
    Fetcher('html-grade',
            'Load page with a browser and check the used external ressources ⏳🔗',
            fetch_external_ressources),
    Fetcher('network',
            'Fetch whois information 🌏',
            fetch_network),
    Fetcher('self-report',
            'Fetch the /status and /config URLs 💡',
            fetch_selfreport),
    Fetcher('https-grade',
            'Check the HTTPS / TLS grade 🔒',
            fetch_cryptcheck),
    Fetcher('csp-grade',
            'Check the CSP grade 📄',
            fetch_mozillaobs),
    Fetcher('timing',
            'Test the response time 🌊🏠🔎🔍🏁❌',
            fetch_timing)
]


async def fetch_using_fetchers(searx_stats_result: SearxStatisticsResult, selected_fetchers: list):
    loop = asyncio.get_event_loop()

    # create a task list from the selected fetchers
    tasks = []
    for fetcher in selected_fetchers:
        task = fetcher.create_task(loop, searx_stats_result)
        tasks.append(task)

    # check if there is a least one task
    if len(tasks) > 0:
        # run everything in parallel
        await asyncio.wait({*tasks})


async def fetch(instance_urls: list, selected_fetchers: list) -> SearxStatisticsResult:
    searx_stats_result = SearxStatisticsResult()

    # initial fetch
    await fetch_from_urls(searx_stats_result, instance_urls)

    # fetch using the selected fetchers
    await fetch_using_fetchers(searx_stats_result, selected_fetchers)

    return searx_stats_result
