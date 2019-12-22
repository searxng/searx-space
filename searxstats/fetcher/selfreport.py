# pylint: disable=invalid-name
import json
from urllib.parse import urljoin
from searxstats.common.utils import dict_merge
from searxstats.common.foreach import for_each
from searxstats.common.http import new_session, get, get_network_type
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import SearxStatisticsResult


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
    async with new_session(network_type=network_type) as session:
        # get config and config
        result_status = await get_status(session, url)
        result_config, result_instance = await get_config(session, url)

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
