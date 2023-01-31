from dataclasses import dataclass
import sys
import traceback
import asyncio
import random
from urllib.parse import urljoin

from lxml import etree
from searxstats.common.utils import exception_to_str
from searxstats.common.html import extract_text, html_fromstring
from searxstats.common.http import new_client, get, get_network_type, NetworkType
from searxstats.common.foreach import for_each
from searxstats.common.memoize import MemoizeToDisk
from searxstats.common.response_time import ResponseTimeStats
from searxstats.config import DEFAULT_COOKIES, DEFAULT_HEADERS
from searxstats.model import SearxStatisticsResult


@dataclass(frozen=True)
class CheckResult:
    results: etree.XPath
    engines: etree.XPath
    # There is no result, error on the main section
    alert_danger_main: etree.XPath
    # There are results, error on the side (above infoboxes)
    alter_danger_side: etree.XPath

    async def _check_html_result_page(self, engine_name, response):
        document = await html_fromstring(response.text)
        result_element_list = self.results(document)
        if len(result_element_list) == 0:
            return False, 'No result'
        for result_element in result_element_list:
            for engine_element in self.engines(result_element):
                if extract_text(engine_element).find(engine_name) >= 0:
                    continue
                return False, f'A result is not from the {engine_name}'
        return True, None

    async def check_google_result(self, response):
        return await self._check_html_result_page('google', response)

    async def check_wikipedia_result(self, response):
        return await self._check_html_result_page('wikipedia', response)

    async def check_search_result(self, response):
        document = await html_fromstring(response.text)
        result_element_list = self.results(document)
        alert_danger_list = self.alert_danger_main(document)
        if len(alert_danger_list) > 0:
            return True, extract_text(alert_danger_list)
        alert_danger_list = self.alter_danger_side(document)
        if len(alert_danger_list) > 0:
            return True, extract_text(alert_danger_list)
        if len(result_element_list) == 0:
            return False, 'No result'
        if len(result_element_list) == 1:
            return False, 'Only one result'
        if len(result_element_list) == 2:
            return False, 'Only two results'
        return True, None


CheckResultByTheme = {
    'simple': CheckResult(
        results=etree.XPath("//div[@id='urls']//article"),
        engines=etree.XPath("//div[contains(@class, 'engines')]/span"),
        alert_danger_main=etree.XPath("//div[@id='urls']/div[contains(@class, 'dialog-error')]"),
        alter_danger_side=etree.XPath("//div[@id='sidebar']/div[contains(@class, 'dialog-error')]"),
    ),
    'oscar': CheckResult(
        results=etree.XPath("//div[@id='main_results']/div[contains(@class,'result-default')]"),
        engines=etree.XPath("//span[contains(@class, 'label label-default')]"),
        alert_danger_main=etree.XPath("//div[contains(@class, 'alert-danger')]/p[2]"),
        alter_danger_side=etree.XPath("//div[contains(@class, 'alert-danger')]/text()"),
    ),
}


async def check_results_always_valid(_):
    return True, None


# pylint: disable=too-many-arguments, too-many-locals
async def request_stat(client, url, count, between_a, and_b, check_results, **kwargs):
    error_count = 0
    response_time_stats = ResponseTimeStats()
    check_results = check_results or check_results_always_valid
    # loop
    for _ in range(0, count):
        await asyncio.sleep(random.randint(a=between_a, b=and_b))
        response, error_msg = await get(client, url, **kwargs)

        # check error_msg
        if error_msg is not None:
            response_time_stats.add_error(error_msg)
        else:
            await response.aread()
            # check response
            valid_response, error_msg = await check_results(response)
            if valid_response:
                response_time_stats.add_response(response)
            else:
                response_time_stats.add_error(error_msg)
                error_count += 1
                if error_count > 3:
                    break
    return response_time_stats.get()


async def request_stat_with_log(instance, obj, key, *args, **kwargs):
    result = await request_stat(*args, **kwargs)
    obj[key] = result
    if 'error' in result:
        print(f'❌ {str(instance)}: {key}: {result["error"]}')


async def get_cookie_settings(client, url):
    # an user request without outgoing request:
    # currency will never match "ip".
    kwargs = {
        'params': {'q': '!currency ip'},
        'headers': DEFAULT_HEADERS,
        'cookies': DEFAULT_COOKIES,
    }

    _, error_msg = await get(client, url, **kwargs)
    if error_msg is not None and error_msg.startswith('HTTP status code 5'):
        # cookie settings may cause a server error: disable them and try again
        del kwargs['cookies']
        _, error_msg = await get(client, url, **kwargs)
        if error_msg is None:
            # no more error: cookies are (most probably) the cause.
            return None
        else:
            # there is still an error
            # disable cookie
            return None
    return DEFAULT_COOKIES


# pylint: disable=unused-argument
def only_instance_url(instance_url, _):
    return instance_url


@MemoizeToDisk(func_key=only_instance_url, expire_time=3600)
async def fetch_one(instance_url: str, detail) -> dict:
    timing = {}
    try:
        network_type = get_network_type(instance_url)
        timeout = 15 if network_type == NetworkType.NORMAL else 30
        async with new_client(timeout=timeout, network_type=network_type) as client:
            # check if cookie settings is supported
            # intended side effect: add one HTTP connection to the pool
            cookies = await get_cookie_settings(client, instance_url)

            # /search instead of / : https://github.com/searx/searx/pull/1681
            search_url = urljoin(instance_url, 'search')
            theme = 'simple' if detail['generator'] == 'searxng' else 'oscar'
            print(search_url, '(', theme, ')')
            check_result = CheckResultByTheme[theme]
            default_params = {'theme': theme}

            # check the default engines
            print('🔎 ' + instance_url)
            await request_stat_with_log(search_url, timing, 'search',
                                        client, instance_url,
                                        3, 120, 160, check_result.check_search_result,
                                        params={'q': 'time', **default_params},
                                        cookies=cookies, headers=DEFAULT_HEADERS)

            # check the google engine
            print('🔍 ' + instance_url)
            await request_stat_with_log(search_url, timing, 'search_go',
                                        client, instance_url,
                                        2, 60, 160, check_result.check_google_result,
                                        params={'q': '!google time', **default_params},
                                        cookies=cookies, headers=DEFAULT_HEADERS)
    except Exception as ex:
        print('❌❌ {0}: unexpected {1} {2}'.format(str(instance_url), type(ex), str(ex)))
        timing['error'] = exception_to_str(ex)
        traceback.print_exc(file=sys.stdout)
    else:
        print('🏁 {0}'.format(str(instance_url)))
    return timing


async def fetch_and_set(instance_url: str, detail):
    detail['timing'].update(await fetch_one(instance_url, detail))


async def fetch(searx_stats_result: SearxStatisticsResult):
    await for_each(searx_stats_result.iter_instances(valid_or_private=True),
                   fetch_and_set, limit=150)
