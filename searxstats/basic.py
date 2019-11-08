import re
import concurrent.futures
from collections import OrderedDict
from searxstats.ssl_utils import get_sslinfo
from searxstats.utils import get_host, new_session, do_get
from searxstats.config import DEFAULT_HEADERS
from searxstats.memoize import MemoizeToDisk


# in a HTML page produced by searx, regex to find the searx version
SEARX_VERSION_RE = r'<meta name=[\"]?generator[\"]? content="searx/([^\"]+)">'


async def get_searx_version(response):
    results = re.findall(SEARX_VERSION_RE, response.text)
    if len(results) > 0 and len(results[0]) > 0:
        return results[0]
    else:
        return None


@MemoizeToDisk()
async def fetch_one(instance_url):
    result = dict()
    # no cookie ( cookies=DEFAULT_COOKIES,  )
    try:
        async with new_session() as session:
            response, error = await do_get(session, instance_url,
                                           headers=DEFAULT_HEADERS, timeout=5)
            # FIXME if status_code is 500 try without theme (but disable checking results)
            if response is not None:
                version = await get_searx_version(response)
                result = {
                    'http': {
                        'status_code': response.status_code,
                        'error': error
                    },
                    'version': version,
                    'timing': {
                        'initial': response.elapsed.total_seconds()
                    }
                }
                # redirect
                response_url = str(response.url)
                if not response_url.endswith('/'):
                    response_url = response_url + '/'
                if response_url != instance_url:
                    result['redirect_from'] = [instance_url]
                    instance_url = response_url
            else:
                result = {
                    'http': {
                    },
                    'version': None,
                    'timing': {
                    }
                }
    except concurrent.futures.TimeoutError:
        result['error'] = 'Timeout error'

    if error is not None:
        result['error'] = error

    result['tls'] = get_sslinfo(get_host(instance_url))

    return instance_url, result


async def fetch_from_urls(instances):
    results = OrderedDict()
    for instance in instances:
        # basic checks
        # url may be different because of redirect
        url, result = await fetch_one(instance)
        if url in results:
            results[url].update(result)
        else:
            results[url] = result
        # output
        http_status_code = result.get('http').get('status_code', '')
        searx_version = result.get('version', '') or ''
        timing = result.get('timing', {}).get('initial') or None
        cert_orgname = (result.get('tls') or {}).get(
            'certificate', {}).get('organizationName', '')
        error = result.get('error', '')
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
    return results
