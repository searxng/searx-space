import os
import time
import traceback
import sys

from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from searxstats.config import BROWSER_LOAD_TIMEOUT
from searxstats.data.well_kown_hashes import WELL_KNOWN_HASHES
from searxstats.data.inline_hashes import INLINE_HASHES
from searxstats.memoize import MemoizeToDisk


WELL_KNOWN_HASHES.update(INLINE_HASHES)


with open(os.path.dirname(os.path.realpath(__file__))
          + "/external_ressources.js", 'r', encoding='utf-8') as f:
    FETCH_RESSOURCE_HASHES_JS = f.read()


def new_driver():
    firefox_profile = webdriver.FirefoxProfile()
    firefox_profile.set_preference("browser.preferences.instantApply", True)
    firefox_profile.set_preference("browser.helperApps.alwaysAsk.force", False)
    firefox_profile.set_preference(
        "browser.download.manager.showWhenStarting", False)
    firefox_profile.set_preference("browser.download.folderList", 0)

    options = Options()
    options.add_argument('--headless')

    return webdriver.Firefox(options=options,
                             firefox_profile=firefox_profile,
                             service_log_path=os.path.devnull)


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


def fetch_ressource_hashes_js(url, driver=None):
    print('⏳', end='', flush=True)
    try:
        # load page
        driver.get(url)

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
                print('.', end='', flush=True)
        return ressources
    except Exception as ex:
        traceback.print_exc(file=sys.stdout)
        return {
            'error': str(ex)
        }


def replace_hash_by_hashref(result, hashes):
    """
    Update 'unknown' field for each hash.
    Update hashes with one ressource set.

    Return hashes of unknown ressources
    """
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
                        new_hash_desc['unknown'] = True
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


def fetch_ressource_hashes(url, ressource_hashes, driver=None):
    ressources = fetch_ressource_hashes_js(url, driver=driver)
    replace_hash_by_hashref(ressources, ressource_hashes)
    return ressources


def analyze_ressources(ressources, hashes):
    # FIXME return only values, not grade
    ressource_count = 0
    well_known_count = 0
    one_unknown_is_used_by_x_instances = None
    grade = None
    for ressource, ressource_type in result_hash_iterator(ressources):
        ressource_count = ressource_count + 1
        # Check external URL, if yes grade F
        if ressource.get('external'):
            grade = 'F'
            break
        # unfetched ressource
        if ressource.get('notFetched', False):
            if ressource_type in ['script', 'inline_script']:
                # unfetched script : impossible to know the grade
                grade = '?'
                break
            # otherwise : skip this ressource (may be dangerous)
            continue
        # check if the hash exists = not error fetching the content
        hash_ref = ressource.get('hashRef')
        if hash_ref is None:
            grade = '?'
            break
        # update one_unknown_is_used_by_x_instances or well_known_count
        res_hash = hashes[hash_ref]
        if res_hash.get('unknown'):
            if ressource_type in ['script', 'inline_script']:
                # check the unknown content only for the scripts (external, internal)
                if one_unknown_is_used_by_x_instances is None:
                    one_unknown_is_used_by_x_instances = res_hash['count']
                else:
                    one_unknown_is_used_by_x_instances = min(one_unknown_is_used_by_x_instances, res_hash['count'])
        else:
            well_known_count = well_known_count + 1
    return grade, ressource_count, one_unknown_is_used_by_x_instances, well_known_count


def get_grade(ressources, hashes):
    """
    A - Only well known content

    B - At least 4 other instances share the same content

    D - At least another instance shares the same content

    E - Only this instance has a content

    F - There is an external link
    """
    grade, ressource_count, one_unknown_is_used_by_x_instances, well_known_count =\
        analyze_ressources(ressources, hashes)

    if grade is None:
        if ressource_count == 0:
            # Nothing, most problably a problem occured while fetching the ressources
            # FIXME check if there is no ressources at all
            grade = '?'
        elif one_unknown_is_used_by_x_instances is None and well_known_count > 0:
            # Only well known content
            grade = 'A'
        elif one_unknown_is_used_by_x_instances >= 5:
            # At least 4 other instances share the same content
            grade = 'B'
        elif one_unknown_is_used_by_x_instances >= 2:
            # At least another instances share the same content
            grade = 'D'
        elif one_unknown_is_used_by_x_instances == 1:
            # Only this instance has a content
            grade = 'E'
    return grade


# pylint: disable=unsubscriptable-object, unsupported-delete-operation, unsupported-assignment-operation
# pylint thinks that ressource_desc is None
def fetch(searx_json):
    ressource_hashes = {
        'index': 0
    }
    instance_details = searx_json['instances']

    driver = new_driver()
    driver.set_page_load_timeout(BROWSER_LOAD_TIMEOUT)
    try:
        for url in instance_details:
            version = instance_details[url].get('version')
            if version is not None and len(version) > 0:
                ressources = fetch_ressource_hashes(url, ressource_hashes, driver=driver)
                instance_details[url]['html'] = {
                    'ressources': ressources
                }
                print('\n🔗 {0:60} {1:3} external js {2:3} inline js'.format(url, len(
                    ressources.get('script', [])), len(ressources.get('inline_script', []))))
    finally:
        print('', flush=True)
        driver.quit()

    # optimize output
    searx_json['hashes'] = [None] * ressource_hashes['index']
    for ressource_hash, ressource_desc in ressource_hashes.items():
        if ressource_hash != 'index':
            i = ressource_desc['index']
            del ressource_desc['index']
            ressource_desc['hash'] = ressource_hash
            searx_json['hashes'][i] = ressource_desc

    # get grade
    for url in instance_details:
        version = instance_details[url].get('version')
        if version is not None and len(version) > 0:
            instance_details[url]['html']['grade'] = get_grade(
                instance_details[url]['html']['ressources'], searx_json['hashes'])
