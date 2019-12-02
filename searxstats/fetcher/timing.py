import sys
import traceback
import asyncio
import random
import statistics
import httpx

from lxml import etree
from searxstats.common.utils import exception_to_str
from searxstats.common.html import extract_text, html_fromstring
from searxstats.common.http import new_session, get
from searxstats.common.memoize import MemoizeToDisk
from searxstats.config import REQUEST_COUNT, DEFAULT_COOKIES, DEFAULT_HEADERS
from searxstats.model import create_fetch


RESULTS_XPATH = etree.XPath(
    "//div[@id='main_results']/div[contains(@class,'result-default')]")
ENGINE_XPATH = etree.XPath("//span[contains(@class, 'label')]")


class RequestErrorException(Exception):
    pass


async def check_html_result_page(engine_name, response):
    document = await html_fromstring(response.text)
    result_element_list = RESULTS_XPATH(document)
    if len(result_element_list) == 0:
        return False
    for result_element in result_element_list:
        for engine_element in ENGINE_XPATH(result_element):
            if extract_text(engine_element).find(engine_name) >= 0:
                continue
            return False
    return True


async def check_google_result(response):
    return await check_html_result_page('google', response)


async def check_wikipedia_result(response):
    return await check_html_result_page('wikipedia', response)


def parse_server_timings(server_timing):
    """
    Parse the Server-Timing header
    See
    - https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Server-Timing
    - https://w3c.github.io/server-timing/#the-server-timing-header-field
    """
    if server_timing == '':
        return dict()

    def parse_param(param):
        """
        Parse `dur=2067.665` or `desc="Total time"`

        Convert `dur` param to second from millisecond
        """
        param = tuple(param.strip().split('='))
        if param[0] == 'dur':
            return param[0], float(param[1]) / 1000
        else:
            return param[0], param[1]

    def parse_metric(str_metric):
        """
        Parse
        - `total;dur=2067.665;desc="Total time"`
        - or `total_0_ddg;dur=512.808` etc..
        """
        str_metric = str_metric.strip().split(';')
        name = str_metric[0].strip()
        param_tuples = map(parse_param, str_metric[1:])
        params = dict(param_tuples)
        return name, params

    raw_timing_list = server_timing.split(',')
    timing_list = list(map(parse_metric, raw_timing_list))
    return dict(timing_list)


def timings_stats(timings):
    if len(timings) >= 2:
        return {
            'median': statistics.median(timings),
            'stdev': statistics.stdev(timings),
            'mean': statistics.mean(timings)
        }
    elif len(timings) == 1:
        return {
            'value': timings
        }
    else:
        return None


def set_timings_stats(result, key, timings):
    stats = timings_stats(timings)
    if stats is not None:
        result[key] = stats


def get_load_time(one_server_timings):
    load_key = list(filter(lambda k: k.startswith('load_0_'), one_server_timings.keys()))
    if len(load_key) > 0:
        return one_server_timings[load_key[0]].get('dur', None)
    else:
        return None


# pylint: disable=too-many-arguments, too-many-locals
async def request_stat(session, url, count, between_a, and_b, check_results, **kwargs):
    all_timings = []
    server_timings = []
    load_timings = []

    headers = kwargs.get('headers', dict())
    headers.update(DEFAULT_HEADERS)
    kwargs['headers'] = headers

    cookies = kwargs.get('cookies', dict())
    cookies.update(DEFAULT_COOKIES)
    kwargs['cookies'] = cookies

    error = None
    error_count = 0
    loop_count = 0

    for i in range(0, count):
        loop_count += 1
        await asyncio.sleep(random.randint(a=between_a, b=and_b))
        response, error = await get(session, url, **kwargs)
        if i == 0 and error is not None and error.startswith('HTTP status code 5'):
            # cookie settings may cause a server error: disable them and try again
            # check only on the first request
            del kwargs['cookies']
            response, error = await get(session, url, **kwargs)
        if error is not None:
            break
        await response.read()
        if (not check_results) or (check_results and (await check_results(response))):
            all_timings.append(response.elapsed.total_seconds())
            server_timing_values = parse_server_timings(response.headers.get('server-timing', ''))
            server_time = server_timing_values.get('total', {}).get('dur', None)
            if server_time is not None:
                server_timings.append(server_time)
            load_time = get_load_time(server_timing_values)
            if load_time is not None:
                load_timings.append(load_time)
        else:
            error = 'Check failed'
            error_count += 1
            if error_count > 3:
                break
    result = {
        'success_percentage': round(len(all_timings) * 100 / loop_count, 0)
    }
    set_timings_stats(result, 'all', all_timings)
    set_timings_stats(result, 'server', server_timings)
    set_timings_stats(result, 'load', load_timings)
    if error is not None:
        result['error'] = error
    return result


async def request_stat_with_exception(obj, key, *args, **kwargs):
    result = await request_stat(*args, **kwargs)
    obj[key] = result
    if 'error' in result:
        raise RequestErrorException(result['error'])


@MemoizeToDisk()
async def fetch_one(instance: str) -> dict:
    timings = {}
    try:
        # FIXME httpx.exceptions.PoolTimeout but only one request at a time for the pool
        user_pool_limits = httpx.PoolLimits(soft_limit=10, hard_limit=300, pool_timeout=5.0)
        async with new_session(pool_limits=user_pool_limits) as session:
            # check index with a new connection each time
            print('🏠 ' + instance)
            await request_stat_with_exception(timings, 'index',
                                              session, instance,
                                              REQUEST_COUNT, 20, 40, None)
            # check wikipedia engine with a new connection each time
            print('🔎 ' + instance)
            await request_stat_with_exception(timings, 'search_wp',
                                              session, instance,
                                              REQUEST_COUNT, 30, 60, check_wikipedia_result,
                                              params={'q': '!wp time'})
            # check google engine with a new connection each time
            print('🔍 ' + instance)
            await request_stat_with_exception(timings, 'search_go',
                                              session, instance,
                                              2, 60, 80, check_google_result,
                                              params={'q': '!google time'})
    except RequestErrorException as ex:
        print('❌ {0}: {1}'.format(str(instance), str(ex)))
    except Exception as ex:
        print('❌❌ {0}: unexpected {1} {2}'.format(str(instance), type(ex), str(ex)))
        timings['error'] = exception_to_str(ex)
        traceback.print_exc(file=sys.stdout)
    else:
        print('🏁 {0}'.format(str(instance)))
    return timings


# pylint: disable=invalid-name
fetch = create_fetch(['timing'], fetch_one, valid_instance=True, limit=70)
