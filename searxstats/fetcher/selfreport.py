# pylint: disable=invalid-name
import json
from urllib.parse import urljoin
from lxml import etree
from searxstats.common.utils import dict_merge
from searxstats.common.foreach import for_each
from searxstats.common.http import new_client, get, get_network_type
from searxstats.common.html import html_fromstring, extract_text
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import SearxStatisticsResult


STATS_ENGINES_XPATH = etree.XPath(
    "//div[@class='col-xs-12 col-sm-12 col-md-6'][3]//div[@class='row']")
STATS_ENGINES_NAME_XPATH = etree.XPath("div[@class='col-sm-4 col-md-4'][1]")
STATS_ENGINES_COUNT_XPATH = etree.XPath("div[@class='col-sm-8 col-md-8'][1]")


# pylint: disable=unused-argument
def get_usable_engines_key(_, instance_url):
    return instance_url


@MemoizeToDisk(func_key=get_usable_engines_key)
async def get_status(session, instance_url):
    result = None
    response, error = await get(session, urljoin(instance_url, 'status'), timeout=5)
    if response is not None and error is None:
        result = []
        try:
            status_json = response.json()
        except json.JSONDecodeError:
            pass
        else:
            result = status_json.get('engines_state', {})
            for engine in result:
                if 'error' in engine:
                    if engine['error'] is None:
                        del engine['error']
    return result


async def get_stats(session, instance_url):
    result = set()
    response, error = await get(session, urljoin(instance_url, 'stats'), timeout=5)
    if response is not None and error is None:
        html = await html_fromstring(response.text)
        for e in STATS_ENGINES_XPATH(html):
            engine_name = extract_text(STATS_ENGINES_NAME_XPATH(e))
            result_count = extract_text(STATS_ENGINES_COUNT_XPATH(e))
            if result_count not in ['', '0.00'] and engine_name is not None:
                result.add(engine_name)
    return result


@MemoizeToDisk(func_key=get_usable_engines_key)
async def get_stats_multi(session, instance_url):
    result = set()
    # fetch the stats four times because of uwsgi
    # may be not enough to get the statistics from all the uwsgi processes
    # still better than only once
    # see https://github.com/searx/searx/issues/162
    # and https://github.com/searx/searx/issues/199
    for _ in range(4):
        result = result.union(await get_stats(session, instance_url))
    return result


def get_status_from_stats(stats):
    if len(stats) == 0:
        return None
    else:
        status = {}
        for engine_name in stats:
            engine_status = status.setdefault(engine_name, {})
            engine_status['stats'] = True
        return status


@MemoizeToDisk(func_key=get_usable_engines_key)
async def get_config(session, instance_url):
    result_config = None
    result_instance = None
    response, error = await get(session, urljoin(instance_url, 'config'), timeout=5)
    if response is not None and error is None:
        try:
            config = response.json()
        except json.JSONDecodeError:
            pass
        else:
            result_config = {
                'engines': {},
                'categories': []
            }
            result_instance = {}
            # categories
            for category in config.get('categories', {}):
                if category not in result_config['categories']:
                    result_config['categories'].append(category)
            # engines
            for engine in config.get('engines', {}):
                # FIXME: deal with different the different configurations among instances for the same engine
                result_config['engines'][engine['name']] = {
                    'categories': engine['categories'],
                    'language_support': engine['language_support'],
                    'paging': engine['paging'],
                    'safesearch': engine['safesearch'],
                    'time_range_support': engine['time_range_support'],
                    'shortcut': engine['shortcut']
                }
                result_instance[engine['name']] = {}
                if engine['enabled']:
                    result_instance[engine['name']]['enabled'] = True
    return result_config, result_instance


async def fetch_one(searx_stats_result: SearxStatisticsResult, url: str, detail):
    network_type = get_network_type(url)
    async with new_client(network_type=network_type) as session:
        # get config and config
        result_status = await get_status(session, url)
        result_config, result_instance = await get_config(session, url)
        if result_status is None:
            result_stats = await get_stats_multi(session, url)
            result_status = get_status_from_stats(result_stats)

        # update config and status for the instance
        detail_engines = detail.setdefault('engines', dict())
        if result_instance is not None:
            dict_merge(detail_engines, result_instance)
        if result_status is not None:
            dict_merge(detail_engines, result_status)

        # update existing engine and category list
        if result_config is not None:
            # engines
            searx_stats_result.engines.update(result_config['engines'])
            # categories
            for category in result_config['categories']:
                if category not in searx_stats_result.categories:
                    searx_stats_result.categories.append(category)
        print('💡 {0:30}'.format(url))


async def fetch(searx_stats_result: SearxStatisticsResult):
    await for_each(searx_stats_result.iter_instances(only_valid=True), fetch_one, searx_stats_result)
