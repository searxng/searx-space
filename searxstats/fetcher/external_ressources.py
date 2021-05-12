import typing
import os
import time
import traceback
import sys

from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from searxstats.config import SEARX_GIT_REPOSITORY, \
                              BROWSER_LOAD_TIMEOUT, TOR_SOCKS_PROXY_HOST, TOR_SOCKS_PROXY_PORT,\
                              get_geckodriver_file_name
from searxstats.data.well_kown_hashes import get_repositories_for_content_sha
from searxstats.data.inline_hashes import INLINE_HASHES
from searxstats.data.dynamic_hashes import DYNAMIC_HASHES
from searxstats.common.http import get_network_type, NetworkType
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import SearxStatisticsResult


WELL_KNOWN_HASHES: typing.Set[str] = set()


def initialize():
    global WELL_KNOWN_HASHES  # pylint: disable=global-statement
    WELL_KNOWN_HASHES.update(INLINE_HASHES)
    WELL_KNOWN_HASHES.update(DYNAMIC_HASHES)


with open(os.path.dirname(os.path.realpath(__file__))
          + "/external_ressources.js", 'r', encoding='utf-8') as f:
    FETCH_RESSOURCE_HASHES_JS = f.read()


# https://raw.githubusercontent.com/dchest/fast-sha256-js/master/sha256.js
with open(os.path.dirname(os.path.realpath(__file__))
          + "/sha256.js", 'r', encoding='utf-8') as f:
    SHA256_JS = f.read()


def new_driver(network_type=NetworkType.NORMAL):
    firefox_profile = webdriver.FirefoxProfile()
    firefox_profile.set_preference('javascript.options.showInConsole', True)
    firefox_profile.set_preference('browser.preferences.instantApply', True)
    firefox_profile.set_preference('browser.helperApps.alwaysAsk.force', False)
    firefox_profile.set_preference('browser.download.manager.showWhenStarting', False)
    firefox_profile.set_preference('browser.download.folderList', 0)
    firefox_profile.accept_untrusted_certs = False
    if network_type == NetworkType.NORMAL:
        pass
    elif network_type == NetworkType.TOR:
        firefox_profile.set_preference('network.proxy.type', 1)
        firefox_profile.set_preference('network.proxy.socks', TOR_SOCKS_PROXY_HOST)
        firefox_profile.set_preference('network.proxy.socks_port', TOR_SOCKS_PROXY_PORT)
        firefox_profile.set_preference('network.proxy.socks_remote_dns', True)
    firefox_profile.update_preferences()
    options = Options()
    options.add_argument('--headless')

    driver = webdriver.Firefox(options=options,
                               firefox_profile=firefox_profile,
                               service_log_path=get_geckodriver_file_name(),
                               service_args=['--log', 'info'])
    driver.set_page_load_timeout(BROWSER_LOAD_TIMEOUT)
    return driver


def get_relative_url(base_url, url):
    if url.startswith(base_url):
        return url[len(base_url):]
    else:
        return url


def result_hash_iterator(result):
    if isinstance(result, dict):
        for ressource_type in result:
            ressources = result[ressource_type]
            if isinstance(ressources, list):
                for ressource in ressources:
                    yield ressource, ressource_type
            elif isinstance(ressources, dict):
                for ressource_url in ressources:
                    yield ressources[ressource_url], ressource_type


# pylint: disable=unused-argument
def fetch_ressource_hashes_js_key(driver, url):
    return url


@MemoizeToDisk(func_key=fetch_ressource_hashes_js_key)
def fetch_ressource_hashes_js(driver, url):
    try:
        # load page
        driver.get(url)

        # http:// website don't have crypt.subtle (.onion)
        # Load fast-sha256 fallback
        driver.execute_script(SHA256_JS)

        # extract external ressources (use fetch Javascript function)
        # HACK: await is the solution
        # Here, Python waits for Firefox and check every second if the result is available
        callback_script = driver.execute_script(FETCH_RESSOURCE_HASHES_JS)
        ressources = None
        retry_count = 0
        wait_result = True
        while wait_result:
            time.sleep(1)
            ressources = driver.execute_script(callback_script)
            if ressources is not None:
                wait_result = False
            elif retry_count >= 10:
                ressources = {}
                wait_result = False
            else:
                retry_count += 1
        return ressources
    except Exception as ex:
        traceback.print_exc(file=sys.stdout)
        return {
            'error': str(ex)
        }


def replace_hash_by_hashref(result, hashes, forks):
    """
    Update 'unknown' field for each hash.
    Update hashes with one ressource set.

    Return hashes of unknown ressources
    """
    # pylint: disable=too-many-nested-blocks
    global WELL_KNOWN_HASHES  # pylint: disable=global-statement
    ressource_hashes = set()
    for ressource, _ in result_hash_iterator(result):
        ressource_hash = ressource.get('hash', None)
        if ressource_hash is not None:
            if ressource_hash not in ressource_hashes:
                # ressource_hash first seen for this instance
                ressource_hashes.add(ressource_hash)
                if ressource_hash not in hashes:
                    new_hash_desc = {
                        'count': 1,
                        'index': hashes['index']
                    }
                    # unknown hash ?
                    if ressource_hash not in WELL_KNOWN_HASHES:
                        repo_url_list = get_repositories_for_content_sha(ressource_hash)
                        if not repo_url_list:
                            new_hash_desc['unknown'] = True
                        elif SEARX_GIT_REPOSITORY not in repo_url_list:
                            new_hash_desc['forks'] = [forks.index(f) for f in repo_url_list]
                    # ressource_hash first seen for the whole run
                    hashes[ressource_hash] = new_hash_desc
                    # the next hash will uses the next index
                    hashes['index'] += 1
                else:
                    # ressource_hash already seen but not in this instance
                    hashes[ressource_hash]['count'] += 1
            # replace the hash field by the hashRef field
            ressource['hashRef'] = hashes[ressource_hash]['index']
            del ressource['hash']


def fetch_ressource_hashes(driver, url, ressource_hashes, forks):
    ressources = fetch_ressource_hashes_js(driver, url)
    replace_hash_by_hashref(ressources, ressource_hashes, forks)
    return ressources


class AnalyzeRessourcesResult:

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


def analyze_ressources(ressources, hashes):
    result = AnalyzeRessourcesResult()
    for ressource, ressource_type in result_hash_iterator(ressources):
        hash_ref = ressource.get('hashRef')
        result.count += 1
        if ressource.get('external'):
            result.external += 1
        elif ressource.get('notFetched', False) or hash_ref is None:
            # if the hashRef does not exists, there was an error fetching the content
            result.unfetched += 1
            if ressource_type in ['script', 'inline_script']:
                result.unfetched_js += 1
        else:
            # update one_unknown_is_used_by_x_instances or well_known_count
            res_hash = hashes[hash_ref]
            if res_hash.get('unknown'):
                result.unknown += 1
                if ressource_type in ['script', 'inline_script']:
                    result.unknown_js += 1
            elif res_hash.get('forks'):
                result.fork += 1
            else:
                result.well_known += 1
    return result


def get_grade(ressources, hashes):
    """
    tags:
    - vanilla: only well known ressources
    - customize: modified ressource, but well known JS
    - customize js: modified ressource including JS
    - external
    """
    result = analyze_ressources(ressources, hashes)

    grade = []

    if result.well_known == result.count:
        # All ressources are well known
        grade.append('V')
    elif result.fork > 0 and result.fork + result.well_known == result.count:
        # It is a fork
        grade.append('F')
    elif result.count == 0:
        # Nothing, most problably a problem occured while fetching the ressources
        # FIXME check if there is no ressources at all
        grade.append('?')
    elif result.external > 0:
        # At least one external ressource
        grade.append('E')
    elif result.unknown_js > 0:
        # Reference to an external javascript (another host)
        grade.append('Cjs')
    elif result.unknown > 0:
        # Reference to an external ressource (another host)
        grade.append('C')
    elif result.unfetched > 0:
        # Error fetching some ressources
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


def fetch_instances(searx_stats_result: SearxStatisticsResult, network_type: NetworkType, ressource_hashes):
    driver = new_driver(network_type=network_type)
    try:
        for url, detail in searx_stats_result.iter_instances(only_valid=True, network_type=network_type):
            if get_network_type(url) == network_type:
                ressources = fetch_ressource_hashes(driver, url, ressource_hashes, searx_stats_result.forks)
                if 'error' in ressources:
                    # don't reuse the browser if there was an error
                    driver.quit()
                    driver = new_driver(network_type=network_type)
                # temporary storage
                detail['html'] = {
                    'ressources': ressources
                }
                # output progress
                external_js = len(ressources.get('script', []))
                inline_js = len(ressources.get('inline_script', []))
                error_msg = ressources.get('error', '').strip()
                print('🔗 {0:60} {1:3} loaded js {2:3} inline js  {3}'.format(url, external_js, inline_js, error_msg))
    finally:
        driver.quit()


# pylint: disable=unsubscriptable-object, unsupported-delete-operation, unsupported-assignment-operation
# pylint thinks that ressource_desc is None
def fetch(searx_stats_result: SearxStatisticsResult):
    ressource_hashes = {
        'index': 0
    }

    for network_type in NetworkType:
        fetch_instances(searx_stats_result, network_type, ressource_hashes)

    # create searx_json['hashes']
    searx_stats_result.hashes = [None] * ressource_hashes['index']
    for ressource_hash, ressource_desc in ressource_hashes.items():
        if ressource_hash != 'index':
            i = ressource_desc['index']
            del ressource_desc['index']
            ressource_desc['hash'] = ressource_hash
            searx_stats_result.hashes[i] = ressource_desc

    # get grade
    for _, detail in searx_stats_result.iter_instances(only_valid=True):
        if 'html' in detail:
            html = detail['html']
            html['grade'] = get_grade(html['ressources'], searx_stats_result.hashes)
