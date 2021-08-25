# pylint: disable=invalid-name
import json
from urllib.parse import urljoin
from searxstats.common.utils import dict_merge
from searxstats.common.foreach import for_each
from searxstats.common.http import new_client, get, get_network_type
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import SearxStatisticsResult


# pylint: disable=unused-argument
def only_instance_url(_, instance_url):
    return instance_url


@MemoizeToDisk(func_key=only_instance_url)
async def get_config(session, instance_url):
    result_engines = None
    result_categories = None
    response, error = await get(session, urljoin(instance_url, 'config'), timeout=5)
    if response is not None and error is None:
        try:
            config = response.json()
        except json.JSONDecodeError:
            pass
        else:
            result_engines = {}
            result_categories = []
            # categories
            for category in config.get('categories', {}):
                if category not in result_categories:
                    result_categories.append(category)
            # engines
            for engine in config.get('engines', {}):
                result_engines[engine['name']] = {
                    'categories': engine['categories'],
                    'language_support': engine['language_support'],
                    'paging': engine['paging'],
                    'safesearch': engine['safesearch'],
                    'time_range_support': engine['time_range_support'],
                    'shortcut': engine['shortcut']
                }
    return result_engines, result_categories


@MemoizeToDisk(func_key=only_instance_url)
async def get_stats_checker(session, instance_url):
    result = None
    response, error = await get(session, urljoin(instance_url, 'stats/checker'), timeout=5)
    if response is not None and error is None:
        try:
            checker_json = response.json()
        except json.JSONDecodeError:
            pass
        else:
            if checker_json.get('status') != 'ok':
                return result
            result = {}
            for engine_name, engine_checker_result in checker_json.get('engines', {}).items():
                result[engine_name] = {
                    'checker': {
                        'success': engine_checker_result.get('success', False),
                        'errors': list(engine_checker_result.get('errors', {}).keys()),
                    }
                }
    return result


@MemoizeToDisk(func_key=only_instance_url)
async def get_stats_errors(session, instance_url):
    # pylint: disable=too-many-nested-blocks
    result = None
    response, error = await get(session, urljoin(instance_url, 'stats/errors'), timeout=5)
    if response is not None and error is None:
        try:
            status_json = response.json()
        except json.JSONDecodeError:
            pass
        else:
            result = {}
            for engine_name, json_errors in status_json.items():
                error_rate = 0
                errors = []
                for error in json_errors:
                    exception_classname = error.get('exception_classname')
                    if exception_classname and not error.get('secondary'):
                        error_rate += error.get('percentage', 0)
                        if error_rate > 0:
                            errors.append(exception_classname)
                # timeout can be count twice:
                # because:
                # * searx.search.processor.* records the timeout
                # * searx.search.search_multiple_requests records the same timeout
                error_rate = min(100, error_rate)
                result[engine_name] = {
                    'error_rate': error_rate,
                    'errors': errors,
                }
    return result


def set_engine_errors(searx_stats_result: SearxStatisticsResult, result_stats_errors: dict):
    engine_errors = searx_stats_result.engine_errors
    for errors in result_stats_errors.values():
        error_indexes = []
        for error in errors.get('errors', {}):
            if error not in engine_errors:
                engine_errors.append(error)
            error_index = engine_errors.index(error)
            if error_index not in error_indexes:
                error_indexes.append(error_index)
        if len(error_indexes):
            errors['errors'] = error_indexes
        else:
            del errors['errors']
    searx_stats_result.engine_errors = engine_errors


async def fetch_one(searx_stats_result: SearxStatisticsResult, url: str, detail):
    network_type = get_network_type(url)
    async with new_client(network_type=network_type) as session:
        # /config
        result_engines, result_categories = await get_config(session, url)
        # /stats/checker
        result_checker = await get_stats_checker(session, url)
        # /stats/errors
        result_stats_errors = await get_stats_errors(session, url)

        # update config and status for the instance
        engine_detail_dict = detail.setdefault('engines', dict())
        if result_engines is not None:
            declared_engines = {engine_name: {} for engine_name in result_engines.keys()}
            dict_merge(engine_detail_dict, declared_engines)
        if result_checker is not None:
            dict_merge(engine_detail_dict, result_checker)
        if result_stats_errors is not None:
            set_engine_errors(searx_stats_result, result_stats_errors)
            dict_merge(engine_detail_dict, result_stats_errors)
        else:
            # impossible to fetch /stats/errors
            # set error_rate to None (unknown) for each engine
            for engine_detail in engine_detail_dict.values():
                engine_detail['error_rate'] = None

        # update existing engine list
        if result_engines is not None:
            for engine_name, engine_detail in result_engines.items():
                if engine_name not in searx_stats_result.engines:
                    engine_detail['stats'] = {
                        # sum of error_rate for all stat_count instance
                        # replace in finalize_stats by error_rate ( = total_error_rate / stats_count )
                        'total_error_rate': 0,
                        # number of instances with this engine
                        'instance_count': 0,
                        # number of instance with this engine and information in /stats/errors or /stats/checker
                        'stats_count': 0,
                    }
                    searx_stats_result.engines[engine_name] = engine_detail
                # FIXME: deal with the different configurations among instances for the same engine
                # update stats
                engine_stat = searx_stats_result.engines[engine_name]['stats']
                engine_stat['instance_count'] += 1
                if result_stats_errors and engine_name in result_stats_errors:
                    engine_stat['total_error_rate'] += result_stats_errors[engine_name].get('error_rate', 0)
                    engine_stat['stats_count'] += 1

        # update existing category list
        if result_categories is not None:
            for category in result_categories:
                if category not in searx_stats_result.categories:
                    searx_stats_result.categories.append(category)
        print('💡 {0:30}'.format(url))


def finalize_stats(searx_stats_result: SearxStatisticsResult):
    for engine_detail in searx_stats_result.engines.values():
        engine_stat = engine_detail.get('stats')
        if engine_stat:
            if engine_stat['stats_count'] == 0:
                engine_stat['error_rate'] = None
            else:
                engine_stat['error_rate'] = round(engine_stat['total_error_rate'] / engine_stat['stats_count'], 1)
            del engine_stat['total_error_rate']


async def fetch(searx_stats_result: SearxStatisticsResult):
    await for_each(searx_stats_result.iter_instances(only_valid=True), fetch_one, searx_stats_result)
    finalize_stats(searx_stats_result)
