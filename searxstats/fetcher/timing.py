import sys
import traceback
import asyncio
import random
import statistics
import httpx

from lxml import etree
from searxstats.utils import extract_text, html_fromstring, exception_to_str
from searxstats.http_utils import new_session, do_get
from searxstats.config import REQUEST_COUNT, DEFAULT_COOKIES, DEFAULT_HEADERS
from searxstats.memoize import MemoizeToDisk
from searxstats.model import SearxStatisticsResult


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
    Parse Server-Timing header
    See https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Server-Timing
    https://w3c.github.io/server-timing/#the-server-timing-header-field
    """
    if server_timing == '':
        return dict()

    def parse_param(param):
        """
        Parse 'dur=2067.665' or 'desc="Total time"'

        Convert 'dur' param to second from millisecond
        """
        param = tuple(param.strip().split('='))
        if param[0] == 'dur':
            return param[0], float(param[1]) / 1000
        else:
            return param[0], param[1]

    def parse_metric(str_metric):
        """
        Parse 'total;dur=2067.665;desc="Total time"' or 'total_0_ddg;dur=512.808' etc..
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
            "median": statistics.median(timings),
            "stdev": statistics.stdev(timings),
            "mean": statistics.mean(timings)
        }
    elif len(timings) == 1:
        return {
            "value": timings
        }
    else:
        return None


# pylint: disable=too-many-arguments, too-many-locals
async def request_stat(session, url, count, between_a, and_b, check_results, **kwargs):
    all_timings = []
    server_timings = []

    headers = kwargs.get('headers', dict())
    headers.update(DEFAULT_HEADERS)
    kwargs['headers'] = headers

    cookies = kwargs.get('cookies', dict())
    cookies.update(DEFAULT_COOKIES)
    kwargs['cookies'] = cookies

    error = None

    for _ in range(0, count):
        await asyncio.sleep(random.randint(a=between_a, b=and_b))
        response, error = await do_get(session, url, **kwargs)
        if error is not None:
            break
        if response.status_code != 200:
            error = "HTTP status code " + str(response.status_code)
            break
        await response.read()
        if (not check_results) or (check_results and (await check_results(response))):
            all_timings.append(response.elapsed.total_seconds())
            one_server_timings = parse_server_timings(response.headers.get('server-timing', ''))
            server_time = one_server_timings.get('total', {}).get('dur', None)
            if server_time is not None:
                server_timings.append(server_time)
        else:
            error = "Check fail"
            break
    result = {
        "success_percentage": round(len(all_timings) * 100 / count, 0)
    }
    all_stats = timings_stats(all_timings)
    if all_stats is not None:
        result["all"] = all_stats
    server_stats = timings_stats(server_timings)
    if server_stats is not None:
        result["server"] = server_stats
    if error is not None:
        result["error"] = error
    return result


async def request_stat_skip_exception(obj, key, *args, **kwargs):
    result = await request_stat(*args, **kwargs)
    obj[key] = result


async def request_stat_with_exception(obj, key, *args, **kwargs):
    result = await request_stat(*args, **kwargs)
    obj[key] = result
    if 'error' in result:
        raise RequestErrorException(result['error'])


# pylint: disable=unused-argument
def bench_instance_key(instance, delay):
    return instance


@MemoizeToDisk(func_key=bench_instance_key)
async def bench_instance(instance: str, delay: float):
    # wait here (avoid to have outgoing traffic jam)
    await asyncio.sleep(delay)
    #
    result = {
        'instance': instance,
        'timing': {}
    }
    try:
        # FIXME httpx.exceptions.PoolTimeout but only one request at a time for the pool
        big_pool_limits = httpx.PoolLimits(soft_limit=10, hard_limit=300, pool_timeout=5.0)
        # check index with a new connection each time
        print('🏠 ' + instance)
        async with new_session(pool_limits=big_pool_limits) as session:
            await request_stat_with_exception(result['timing'], 'index', session,
                                              instance,
                                              REQUEST_COUNT, 4, 15, None)
        # check wikipedia engine with a new connection each time
        print('🔎 ' + instance)
        async with new_session(pool_limits=big_pool_limits) as session:
            await request_stat_with_exception(result['timing'], 'search_wp', session,
                                              instance,
                                              REQUEST_COUNT, 20, 40, check_wikipedia_result,
                                              params={'q': '!wp searx'})
        # check google engine with a new connection each time
        print('🔍 ' + instance)
        async with new_session(pool_limits=big_pool_limits) as session:
            await request_stat_with_exception(result['timing'], 'search_go', session,
                                              instance,
                                              REQUEST_COUNT, 30, 60, check_google_result,
                                              params={'q': '!google searx'})
    except RequestErrorException as ex:
        print('❌ {0}: {1}'.format(str(instance), str(ex)))
        result['timing']['error'] = exception_to_str(ex)
    except Exception as ex:
        print('❌❌ {0}: unexpected {1} {2}'.format(str(instance), type(ex), str(ex)))
        result['timing']['error'] = exception_to_str(ex)
        traceback.print_exc(file=sys.stdout)
    else:
        print('🏁 {0}'.format(str(instance)))
    return result


async def add_timing_batch(searx_stats_result: SearxStatisticsResult, instances_to_process: list):
    future_list = []
    delay = 0
    for instance in instances_to_process:
        instance_co = bench_instance(instance, delay + random.randint(a=0, b=1800) / 1000)
        instance_f = asyncio.ensure_future(instance_co)
        future_list.append(instance_f)
        delay = delay + 1.5

    if len(future_list) > 0:
        partial_results, pending_results = await asyncio.wait({*future_list})
        if len(pending_results) > 0:
            print('❌ {0} pending results', len(pending_results))
        for task in partial_results:
            instance_r = task.result()
            if instance_r is not None and 'timing' in instance_r:
                detail = searx_stats_result.get_instance(instance_r['instance'])
                detail['timing'].update(instance_r['timing'])


async def add_timing_batch_and_print(searx_stats_result: SearxStatisticsResult,
                                     instances_to_process: list, count_from: int, count: int):
    print('\n🌊 [{0} - {1}]'.format(count_from, count))
    return await add_timing_batch(searx_stats_result, instances_to_process)


async def fetch(searx_stats_result: SearxStatisticsResult):
    instances_to_process = []
    count_from = 0
    count = 0
    for url, _ in searx_stats_result.iter_valid_instances():
        instances_to_process.append(url)
        if len(instances_to_process) >= 70:
            await add_timing_batch_and_print(searx_stats_result, instances_to_process, count_from, count)
            instances_to_process = []
            count_from = count + 1
        count = count + 1
    await add_timing_batch_and_print(searx_stats_result, instances_to_process, count_from, count)
