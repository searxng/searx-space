import enum
import calendar
import datetime
import logging
import json
import asyncio
import uvloop

import searxstats.ssl_utils
import searxstats.instances
import searxstats.basic
import searxstats.fetcher.external_ressources
import searxstats.fetcher.network
import searxstats.fetcher.selfreport
import searxstats.fetcher.cryptcheck
import searxstats.fetcher.mozillaobs
import searxstats.fetcher.timing


class ModuleType(enum.Enum):
    SYNC = 0
    ASYNC = 1


MODULE_DEFINITION = [
    {
        'name': 'html-grade',
        'help': 'Load page with a browser and check the used external ressources ⏳🔗',
        'type': ModuleType.SYNC,
        'fetch': searxstats.fetcher.external_ressources.fetch,
    },
    {
        'name': 'network',
        'help': 'Fetch whois information 🌏',
        'type': ModuleType.SYNC,
        'fetch': searxstats.fetcher.network.fetch,
    },
    {
        'name': 'self-report',
        'help': 'Fetch the /status and /config URLs 💡',
        'type': ModuleType.ASYNC,
        'fetch': searxstats.fetcher.selfreport.fetch,
    },
    {
        'name': 'https-grade',
        'help': 'Check the HTTPS / TLS grade 🔒',
        'type': ModuleType.ASYNC,
        'fetch': searxstats.fetcher.cryptcheck.fetch,
    },
    {
        'name': 'csp-grade',
        'help': 'Check the CSP grade 📄',
        'type': ModuleType.ASYNC,
        'fetch': searxstats.fetcher.mozillaobs.fetch,
    },
    {
        'name': 'timing',
        'help': 'Test the response time 🌊🏠🔎🔍🏁❌',
        'type': ModuleType.ASYNC,
        'fetch': searxstats.fetcher.timing.fetch,
    }
]


def initialize():
    logging.basicConfig(level=logging.DEBUG)
    for logger_name in ('httpx.config', 'hpack.hpack', 'hpack.table',
                        'httpx.dispatch.connection_pool', 'httpx.dispatch.connection',
                        'httpx.dispatch.http2', 'httpx.dispatch.http11',
                        'ipwhois.rdap', 'ipwhois.ipwhois', 'ipwhois.net',
                        'selenium.webdriver.remote', 'urllib3.connectionpool'):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    searxstats.ssl_utils.monkey_patch()
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def write_results(output_file_name, searx_json):
    with open(output_file_name, "w") as output_file:
        json.dump(searx_json, output_file, indent=4, ensure_ascii=False)


async def run_once(output_file, instance_urls=None, modules=None):
    # select modules
    if modules is None:
        modules = {}

    selected_modules = list(filter(lambda md: md['name'] in modules, MODULE_DEFINITION))

    # fetch instance list
    if instance_urls is None or len(instance_urls) == 0:
        instance_urls = await searxstats.instances.get_instance_urls()
        print('{0} URLs fetched'.format(len(instance_urls)))

    # initial check
    instance_details = await searxstats.basic.fetch_from_urls(instance_urls)
    searx_json = {
        'timestamp': calendar.timegm(datetime.datetime.now().utctimetuple()),
        'instances': instance_details,
        'hashes': []
    }
    write_results(output_file, searx_json)

    # run sync tasks
    for module in selected_modules:
        if module['type'] == ModuleType.SYNC:
            module['fetch'](searx_json)

    # run async tasks
    loop = asyncio.get_event_loop()
    tasks = []
    for module in selected_modules:
        if module['type'] == ModuleType.ASYNC:
            task = loop.create_task(module['fetch'](searx_json))
            tasks.append(task)

    if len(tasks) > 0:
        await asyncio.wait({*tasks})

    # write results
    write_results(output_file, searx_json)


async def run_server(*args, **kwargs):
    await run_once(*args, **kwargs)
    while True:
        print('\n💤 Sleep until next run\n')
        await asyncio.sleep(24 * 3600)
        await run_once(*args, **kwargs)
