import typing
import os
import time
import traceback
import sys

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from searxstats.config import SEARXNG_GIT_REPOSITORY, \
                              BROWSER_LOAD_TIMEOUT, TOR_SOCKS_PROXY_HOST, TOR_SOCKS_PROXY_PORT, \
                              get_geckodriver_file_name
from searxstats.data import get_repositories_for_content_sha, is_wellknown_content_sha
from searxstats.common.http import NetworkType
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import SearxStatisticsResult


with open(os.path.dirname(os.path.realpath(__file__))
          + "/external_resources.js", 'r', encoding='utf-8') as f:
    FETCH_RESOURCE_HASHES_JS = f.read()


# https://raw.githubusercontent.com/dchest/fast-sha256-js/master/sha256.js
with open(os.path.dirname(os.path.realpath(__file__))
          + "/sha256.js", 'r', encoding='utf-8') as f:
    SHA256_JS = f.read()


def new_driver(network_type=NetworkType.NORMAL):
    options = Options()
    options.add_argument('--headless')
    options.accept_insecure_certs = False
    options.set_preference('javascript.options.showInConsole', True)
    options.set_preference('browser.preferences.instantApply', True)
    options.set_preference('browser.helperApps.alwaysAsk.force', False)
    options.set_preference('browser.download.manager.showWhenStarting', False)
    options.set_preference('browser.download.folderList', 0)
    if network_type == NetworkType.TOR:
        options.set_preference('network.proxy.type', 1)
        options.set_preference('network.proxy.socks', TOR_SOCKS_PROXY_HOST)
        options.set_preference('network.proxy.socks_port', TOR_SOCKS_PROXY_PORT)
        options.set_preference('network.proxy.socks_remote_dns', True)

    service = Service(
        log_output=get_geckodriver_file_name(),
        service_args=['--log', 'info'],
    )
    driver = webdriver.Firefox(options=options, service=service)
    driver.set_page_load_timeout(BROWSER_LOAD_TIMEOUT)
    return driver


def result_hash_iterator(result):
    if isinstance(result, dict):
        for resource_type in result:
            resources = result[resource_type]
            if isinstance(resources, list):
                for resource in resources:
                    yield resource, resource_type
            elif isinstance(resources, dict):
                for resource_url in resources:
                    yield resources[resource_url], resource_type


# pylint: disable=unused-argument
def fetch_resource_hashes_js_key(driver, url):
    return url


@MemoizeToDisk(func_key=fetch_resource_hashes_js_key)
def fetch_resource_hashes_js(driver, url):
    try:
        # load page
        driver.get(url)

        # http:// website don't have crypt.subtle (.onion)
        # Load fast-sha256 fallback
        driver.execute_script(SHA256_JS)

        # extract external resources (use fetch Javascript function)
        # HACK: await is the solution
        # Here, Python waits for Firefox and check every second if the result is available
        callback_script = driver.execute_script(FETCH_RESOURCE_HASHES_JS)
        resources = None
        retry_count = 0
        wait_result = True
        while wait_result:
            time.sleep(1)
            resources = driver.execute_script(callback_script)
            if resources is not None:
                wait_result = False
            elif retry_count >= 10:
                resources = {}
                wait_result = False
            else:
                retry_count += 1
        return resources
    except Exception as ex:
        traceback.print_exc(file=sys.stdout)
        return {
            'error': str(ex)
        }


def _hash_fork_refs(resource_hash, forks):
    if is_wellknown_content_sha(resource_hash):
        return {}
    repo_urls = get_repositories_for_content_sha(resource_hash)
    if not repo_urls:
        return {'unknown': True}
    if SEARXNG_GIT_REPOSITORY in repo_urls:
        return {}
    fork_refs = [forks.index(url) for url in repo_urls if url in forks]
    return {'forks': fork_refs} if fork_refs else {'unknown': True}


def replace_hash_by_hashref(result, hashes, forks):
    """
    Update 'unknown' field for each hash.
    Update hashes with one resource set.

    Return hashes of unknown resources
    """
    # pylint: disable=too-many-nested-blocks
    resource_hashes = set()
    for resource, _ in result_hash_iterator(result):
        resource_hash = resource.get('hash', None)
        if resource_hash is not None:
            if resource_hash not in resource_hashes:
                # resource_hash first seen for this instance
                resource_hashes.add(resource_hash)
                if resource_hash not in hashes:
                    # resource_hash first seen for the whole run
                    hashes[resource_hash] = {
                        'count': 1,
                        'index': hashes['index'],
                        **_hash_fork_refs(resource_hash, forks),
                    }
                    # the next hash will uses the next index
                    hashes['index'] += 1
                else:
                    # resource_hash already seen but not in this instance
                    hashes[resource_hash]['count'] += 1
            # replace the hash field by the hashRef field
            resource['hashRef'] = hashes[resource_hash]['index']
            del resource['hash']


def fetch_resource_hashes(driver, url, resource_hashes, forks):
    resources = fetch_resource_hashes_js(driver, url)
    replace_hash_by_hashref(resources, resource_hashes, forks)
    return resources


class AnalyzeResourcesResult:

    # pylint: disable=too-many-instance-attributes

    __slots__ = 'count', 'well_known', 'fork', 'unknown', 'unknown_js', 'unfetched', 'unfetched_js', 'external'

    def __init__(self):
        self.count = 0
        self.well_known = 0
        self.fork = 0
        self.unknown = 0
        self.unknown_js = 0
        self.unfetched = 0
        self.unfetched_js = 0
        self.external = 0


def analyze_resources(resources, hashes):
    result = AnalyzeResourcesResult()
    for resource, resource_type in result_hash_iterator(resources):
        hash_ref = resource.get('hashRef')
        result.count += 1
        if resource.get('external'):
            result.external += 1
        elif resource.get('notFetched', False) or hash_ref is None:
            # if the hashRef does not exists, there was an error fetching the content
            result.unfetched += 1
            if resource_type in ['script', 'inline_script']:
                result.unfetched_js += 1
        else:
            # update one_unknown_is_used_by_x_instances or well_known_count
            res_hash = hashes[hash_ref]
            if res_hash.get('unknown'):
                result.unknown += 1
                if resource_type in ['script', 'inline_script']:
                    result.unknown_js += 1
            elif res_hash.get('forks'):
                result.fork += 1
            else:
                result.well_known += 1
    return result


def get_grade(resources, hashes, analytics):
    """
    tags:
    - vanilla: only well known resources
    - customize: modified resource, but well known JS
    - customize js: modified resource including JS
    - external
    """
    result = analyze_resources(resources, hashes)

    grade = []

    if analytics:
        # Analytics: same as external resources
        grade.append('👁️')
    elif result.well_known == result.count:
        # All resources are well known
        grade.append('V')
    elif result.fork > 0 and result.fork + result.well_known == result.count:
        # It is a fork
        grade.append('F')
    elif result.count == 0:
        # Nothing, most problably a problem occured while fetching the resources
        # FIXME check if there is no resources at all
        grade.append('?')
    elif result.external > 0:
        # At least one external resource
        grade.append('E')
    elif result.unknown_js > 0:
        # Reference to an external javascript (another host)
        grade.append('Cjs')
    elif result.unknown > 0:
        # Reference to an external resource (another host)
        grade.append('C')
    elif result.unfetched > 0:
        # Error fetching some resources
        # Deal with it later
        pass
    else:
        # Algorithm error: must not happen
        grade.append('Err')

    if result.unfetched_js > 0:
        grade.append('js?')
    elif result.unfetched > 0 and '?' not in grade:
        grade.append('?')

    return ', '.join(grade)


def find_forks(resources, hashes, forks) -> typing.List[str]:
    """From the hashes of the static files, return a list of fork URL.
    sorted by reference: the first URL is the most referenced.
    """
    found_forks: typing.Dict[str, int] = {}
    for resource, _ in result_hash_iterator(resources):
        hash_ref = resource.get('hashRef')
        if 'hashRef' not in resource:
            # the resource was not found / error
            continue
        hash_info = hashes[hash_ref]
        for fork_ref in hash_info.get('forks', []):
            fork_url = forks[fork_ref]
            found_forks[fork_url] = found_forks.get(fork_url, 0) + 1

    # Example:
    # found_forks = {
    #  'https://github.com/searxng/searxng': 7,
    # }

    if found_forks:
        # sort criterias:
        # * give priority to upstream SearXNG
        # * then sort by the number of found hashes in a fork.
        # Example:
        # len(hashes) = 8
        # * 6 hashes exist in fork A
        # * 7 hashes exist in fork B (B is upstream)
        # * 7 hashes exist in fork C (C is not upstream)
        # --> found_fork_tuples = [(B, 7), (C, 7), (A, 6)]
        # --> find_forks returns [B, C, A]
        # possible enhancement:
        # * use the github/gitlab API to detect fork relation
        # * example: https://api.github.com/repos/<org>/<repo> see "parent" key.
        found_fork_tuples = sorted(
            found_forks.items(),
            key=lambda o: (o[0] != SEARXNG_GIT_REPOSITORY, o[1])
        )
        return [f[0] for f in found_fork_tuples]
    return []


def fetch_instances(searx_stats_result: SearxStatisticsResult, network_type: NetworkType, resource_hashes):
    driver = new_driver(network_type=network_type)
    try:
        for url, detail in searx_stats_result.iter_instances(only_valid=True, network_type=network_type):
            resources = fetch_resource_hashes(driver, url, resource_hashes, searx_stats_result.forks)
            resources.setdefault('error', None)
            if resources.get('error'):
                # don't reuse the browser if there was an error
                driver.quit()
                driver = new_driver(network_type=network_type)
            # temporary storage
            detail['html'] = {
                'resources': resources
            }
            # output progress
            external_js = len(resources.get('script', []))
            inline_js = len(resources.get('inline_script', []))
            error_msg = (resources.get('error') or '').strip()
            print('🔗 {0:60} {1:3} loaded js {2:3} inline js  {3}'.format(url, external_js, inline_js, error_msg))
    finally:
        driver.quit()


# pylint: disable=unsubscriptable-object, unsupported-delete-operation, unsupported-assignment-operation
# pylint thinks that resource_desc is None
def fetch(searx_stats_result: SearxStatisticsResult):
    resource_hashes = {
        'index': 0
    }

    for network_type in NetworkType:
        fetch_instances(searx_stats_result, network_type, resource_hashes)

    # create searx_json['hashes']
    searx_stats_result.hashes = [None] * resource_hashes['index']
    for resource_hash, resource_desc in resource_hashes.items():
        if resource_hash != 'index':
            i = resource_desc['index']
            del resource_desc['index']
            resource_desc['hash'] = resource_hash
            searx_stats_result.hashes[i] = resource_desc

    # detect fork using the static files
    for _, detail in searx_stats_result.iter_instances(only_valid=True):
        resources = detail.get('html', {}).get('resources')
        if resources:
            found_forks = find_forks(
                detail['html']['resources'],
                searx_stats_result.hashes,
                searx_stats_result.forks)
            if found_forks and detail['git_url'] not in found_forks:
                detail['git_url'] = found_forks[0]

    # get grade
    for _, detail in searx_stats_result.iter_instances(only_valid=True):
        if 'html' in detail:
            html = detail['html']
            html['grade'] = get_grade(html['resources'], searx_stats_result.hashes, detail['analytics'])
