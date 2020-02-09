# pylint: disable=invalid-name
import re
import concurrent.futures
from searxstats.model import SearxStatisticsResult
from searxstats.common.foreach import for_each
from searxstats.common.utils import dict_merge
from searxstats.common.http import new_client, get, get_host, get_network_type, NetworkType
from searxstats.common.ssl_info import get_ssl_info
from searxstats.common.memoize import MemoizeToDisk
from searxstats.config import DEFAULT_HEADERS


# in a HTML page produced by searx, regex to find the searx version
SEARX_VERSION_RE = r'<meta name=[\"]?generator[\"]? content="searx/([^\"]+)">'


async def get_searx_version(response):
    results = re.findall(SEARX_VERSION_RE, response.text)
    if len(results) > 0 and len(results[0]) > 0:
        return results[0]
    else:
        return None


@MemoizeToDisk(expire_time=3600)
async def fetch_one(instance_url):
    detail = dict()
    # no cookie ( cookies=DEFAULT_COOKIES,  )
    try:
        network_type = get_network_type(instance_url)
        async with new_client(network_type=network_type) as session:
            response, error = await get(session, instance_url,
                                        headers=DEFAULT_HEADERS, timeout=10)
            if response is not None:
                version = await get_searx_version(response)
                detail = {
                    'network_type': network_type.name.lower(),
                    'http': {
                        'status_code': response.status_code,
                        'error': error
                    },
                    'version': version,
                    'timing': {
                        'initial': response.elapsed.total_seconds()
                    },
                }
                response_url = str(response.url)
                # add trailing slash
                if not response_url.endswith('/'):
                    response_url = response_url + '/'
                # redirect
                if 'alternativeUrls' not in detail:
                    detail['alternativeUrls'] = dict()
                if response_url != instance_url:
                    detail['alternativeUrls'][instance_url] = 'redirect from'
                    instance_url = response_url
            else:
                detail = {
                    'network_type': network_type.name.lower(),
                    'http': {
                        'status_code': None,
                        'error': error
                    },
                    'version': None,
                    'timing': {
                    },
                }
    except concurrent.futures.TimeoutError:
        # This exception occurs on new_client()
        detail['error'] = 'Timeout error'

    if error is not None:
        detail['error'] = error

    if network_type == NetworkType.NORMAL:
        detail['tls'] = get_ssl_info(get_host(instance_url))
    return instance_url, detail


async def fetch_one_display(url: str) -> dict:
    # basic checks
    url, detail = await fetch_one(url)

    # output
    http_status_code = detail.get('http').get('status_code', '') or ''
    searx_version = detail.get('version', '') or ''
    timing = detail.get('timing', {}).get('initial') or None
    cert_orgname = (detail.get('tls') or {}).get(
        'certificate', {}).get('organizationName', '')
    error = detail.get('error', '')
    if error != '':
        icon = '❌'
    elif searx_version == '':
        icon = '👽'
    else:
        icon = '🍰'
    if timing:
        timing = '{:.3f}'.format(timing)
    else:
        timing = '     '
    print('{0:3} {1} {2:20} {3} {4:60} {5:30} {6:50}'.
          format(http_status_code, icon, searx_version, timing, url, cert_orgname, error))

    return url, detail


async def fetch(searx_stats_result: SearxStatisticsResult):

    async def fetch_and_set_async(url: str, detail, *_, **__):
        if 'version' not in detail:
            r_url, r_detail = await fetch_one_display(url)
            dict_merge(r_detail, detail)
            if r_url != url:
                del searx_stats_result.instances[url]
            searx_stats_result.update_instance(r_url, r_detail)

    instance_iterator = searx_stats_result.iter_instances(only_valid=False)
    await for_each(instance_iterator, fetch_and_set_async, limit=1)
