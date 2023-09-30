# pylint: disable=invalid-name
import re
import asyncio
import json
import concurrent.futures
from urllib.parse import urljoin
from collections import OrderedDict
from searxstats.model import SearxStatisticsResult
from searxstats.common.foreach import for_each
from searxstats.common.utils import dict_merge
from searxstats.common.http import new_client, get, get_host, get_network_type, NetworkType
from searxstats.common.ssl_info import get_ssl_info
from searxstats.common.memoize import MemoizeToDisk
from searxstats.common.response_time import ResponseTimeStats
from searxstats.data import get_fork_list
from searxstats.config import DEFAULT_HEADERS, SEARX_GIT_REPOSITORY


# in a HTML page produced by SearXNG, regex to find the SearXNG version
HTML_GENERATOR_RE = r'<meta name=[\"]?generator[\"]? content="([^\"]+)">'


async def get_html_meta_generator(response):
    """
    get the version from the <meta> tag
    """
    results = re.findall(HTML_GENERATOR_RE, response.text)
    if len(results) > 0 and len(results[0]) > 0:
        return results[0].lower().split('/')
    return None, None


async def get_searx_config(session, url):
    """
    get the version from the /config URL
    """
    response, error = await get(session, url, headers=DEFAULT_HEADERS, timeout=10)
    if response is not None and error is None:
        try:
            config = response.json()
            return config, None
        except json.JSONDecodeError as e:
            return None, str(e)
    return None, error


async def resolve_https_redirect(session, url):
    if not url or not url.startswith('https://'):
        return None
    response, _error = await get(session, url, timeout=10)
    if response is not None:
        return str(response.url)
    return url


async def set_searx_version(detail, git_url, session, response_url, response):
    url_config = urljoin(response_url, 'config')
    config, error_config = await get_searx_config(session, url_config)
    if error_config:
        if 'comments' not in detail:
            detail['comments'] = []
        detail['comments'].append("Impossible to access {0}: {1}.".format(url_config, error_config))

    generator_name, generator_version = await get_html_meta_generator(response)

    if config and not error_config:
        version = config.get('version')
        if not version:
            version = generator_version
        if not git_url:
            git_url = config.get('brand', {}).get('GIT_URL')
        doc_url = config.get('brand', {}).get('DOCS_URL')
        detail['generator'] = generator_name
        detail['version'] = version
        detail['contact_url'] = config.get('brand', {}).get('CONTACT_URL')
        detail['docs_url'] = await resolve_https_redirect(session, doc_url)
        detail['public_instance'] = config.get('public_instance', False)
        detail['limiter'] = config.get('limiter', {
            'botdetection.ip_limit.link_token':	False,
            'botdetection.ip_lists.pass_searxng_org': False,
            'enabled': False,
        })
    if git_url:
        git_url = await resolve_https_redirect(session, git_url)
    else:
        git_url = SEARX_GIT_REPOSITORY
    detail['git_url'] = git_url


@MemoizeToDisk(expire_time=3600)
async def fetch_one(instance_url: str, git_url: str, private: bool) -> dict:
    # no cookie ( cookies=DEFAULT_COOKIES,  )
    network_type = get_network_type(instance_url)
    detail = {
        'network_type': network_type.name.lower(),
        'http': {
        },
        'version': None,
        'git_url': git_url,
    }
    try:
        async with new_client(network_type=network_type) as session:
            response, error = await get(session, instance_url,
                                        headers=DEFAULT_HEADERS, timeout=10)
            status_code = response.status_code if response is not None else None
            detail['http'] = {
                'status_code': status_code,
                'error': error,
            }
            if response is not None:
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

                # get the SearXNG version
                if error is None:
                    await asyncio.sleep(0.5)
                    await set_searx_version(detail, git_url, session, response_url, response)

                # set initial response time
                detail['timing'] = {}
                response_time_stats = ResponseTimeStats()
                response_time_stats.add_response(response)
                detail['timing']['initial'] = response_time_stats.get()
    except concurrent.futures.TimeoutError:
        # This exception occurs on new_client()
        error = 'Timeout error'

    if (detail['version'] is not None or private) and network_type == NetworkType.NORMAL:
        detail['tls'] = get_ssl_info(get_host(instance_url))

    if error is not None:
        detail['http']['error'] = error
        detail['error'] = error
    elif not detail.get('public_instance', False):
        detail['error'] = 'Not configured as a public instance'

    return instance_url, detail


async def fetch_one_display(url: str, git_url: str, private: bool) -> dict:
    # basic checks
    url, detail = await fetch_one(url, git_url, private)

    # output
    error = detail['http']['error'] or ''
    http_status_code = detail['http'].get('status_code', '') or ''
    searx_version = detail.get('version', '') or ''
    timing = detail.get('timing', {}).get('initial', {}).get('all', {}).get('value', None)
    cert_orgname = detail.get('tls', {}).get('certificate', {}).get('issuer', {}).get('organizationName', '')
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

    url_to_deleted = []
    url_to_update = OrderedDict()

    # fetch and store the changes in url_to_deleted and url_to_add
    # do not modify the searx_stats_result.instances to avoid
    async def fetch_and_store_change(url: str, detail, *_, **__):
        if 'version' not in detail:
            r_url, r_detail = await fetch_one_display(url, detail['git_url'], searx_stats_result.private)
            del detail['git_url']
            dict_merge(r_detail, detail)
            if r_url != url:
                # r_url is the URL after following a HTTP redirect
                # in this case the searx_stats_result.instances[url] must be deleted.
                url_to_deleted.append(url)
            url_to_update[r_url] = r_detail

    instance_iterator = searx_stats_result.iter_instances(only_valid=False, valid_or_private=False)
    await for_each(instance_iterator, fetch_and_store_change, limit=1)

    # apply the changes
    for url in url_to_deleted:
        del searx_stats_result.instances[url]
    for url, detail in url_to_update.items():
        searx_stats_result.update_instance(url, detail)
    # add all known forks
    for fork in get_fork_list():
        if fork not in searx_stats_result.forks:
            searx_stats_result.forks.append(fork)
