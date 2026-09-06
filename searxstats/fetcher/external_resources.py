import typing
import hashlib
import re
import traceback
import sys
from urllib.parse import urljoin

from curl_cffi.requests import Session
from lxml import html as lxml_html

from searxstats.config import SEARXNG_GIT_REPOSITORY, \
                              BROWSER_LOAD_TIMEOUT, TOR_SOCKS_PROXY_HOST, TOR_SOCKS_PROXY_PORT
from searxstats.data import get_repositories_for_content_sha, is_wellknown_content_sha
from searxstats.common.http import NetworkType
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import SearxStatisticsResult


# import(`./chunk/CFmKEewG.min.js`)
_IMPORT_RE = re.compile(r'''(?:import\s*\(\s*|import\s+|from\s+)['"`]([^'"`]+)['"`]''')
# url(./img/searxng.png)
_CSS_URL_RE = re.compile(r'''url\(\s*['"]?([^'")]+)['"]?\s*\)''')
# data:image/svg+xml;charset=UTF-8
# javascript:
# blob:
# href="#"
_SKIP_HREF = ('data:', 'javascript:', 'blob:', '#')
# rel="canonical"
# rel="alternate" type="application/rss+xml"
# rel="search" href="/opensearch.xml"
# rel="dns-prefetch"
# rel="preconnect"
# rel="manifest" href="/manifest.json"
_META_REL = {'canonical', 'alternate', 'search', 'dns-prefetch', 'preconnect', 'manifest'}


def new_session(network_type=NetworkType.NORMAL):
    tor = network_type == NetworkType.TOR
    return Session(
        impersonate='tor' if tor else 'firefox',
        timeout=BROWSER_LOAD_TIMEOUT,
        proxy=f'socks5h://{TOR_SOCKS_PROXY_HOST}:{TOR_SOCKS_PROXY_PORT}' if tor else None,
    )


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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rel_tokens(rel):
    if isinstance(rel, (list, tuple)):
        return {token.lower() for token in rel}
    return set((rel or '').lower().split())


def _inline_hashes(tree, xpath):
    return [{'hash': _sha256(text.encode('utf-8'))}
            for text in tree.xpath(xpath) if isinstance(text, str) and text]


def _seeds(tree, page_url):
    # custom logo on some instances
    seeds = [('script', el.get('src'), page_url) for el in tree.xpath('//script[@src]')]
    for el in tree.xpath('//link[@href]'):
        if not _rel_tokens(el.get('rel')) & _META_REL:
            seeds.append(('link', el.get('href'), page_url))
    for tag in ('img', 'iframe'):
        seeds.extend((tag, el.get('src'), page_url) for el in tree.xpath(f'//{tag}[@src]'))
    for text in tree.xpath('//style/text()'):
        if isinstance(text, str):
            seeds.extend(('css', ref, page_url) for ref in _CSS_URL_RE.findall(text))
    for style in tree.xpath('//@style'):
        seeds.extend(('css', ref, page_url) for ref in _CSS_URL_RE.findall(style))
    return seeds


def _nested(url, response):
    # scripts imported after load
    # or images referenced from CSS
    ctype = (response.headers.get('content-type') or '').lower()
    if 'javascript' in ctype or 'ecmascript' in ctype:
        return [('link', ref, url) for ref in _IMPORT_RE.findall(response.text)
                if ref.startswith(('.', '/', 'http://', 'https://'))]
    if 'css' in ctype:
        return [('css', ref, url) for ref in _CSS_URL_RE.findall(response.text)]
    return []


def _collect(session, page_url, pending):
    resources, seen = {}, set()
    while pending:
        kind, href, base = pending.pop()
        if not href or href.startswith(_SKIP_HREF):
            continue
        url = urljoin(base, href)
        if url in seen:
            continue
        seen.add(url)
        # if not a subpath of the URL, it is external
        info = {} if url.startswith(page_url) else {'external': True}
        try:
            response = session.get(url)
            if response.status_code != 200:
                info.update(notFetched=True, error=f'HTTP status {response.status_code}: {response.reason}')
            else:
                info['hash'] = _sha256(response.content)
                pending.extend(_nested(url, response))
        except Exception as ex:  # pylint: disable=broad-except
            info.update(notFetched=True, error=str(ex).partition('. See ')[0])
        key = url[len(page_url):] if url.startswith(page_url) else url
        resources.setdefault(kind, {})[key] = info
    return resources


# pylint: disable=unused-argument
def fetch_page_resources_key(session, url):
    return url


@MemoizeToDisk(func_key=fetch_page_resources_key)
def fetch_page_resources(session, url):
    try:
        response = session.get(url)
        if response.status_code != 200:
            return {'error': f'HTTP status code {response.status_code}'}
        page_url = str(response.url)
        tree = lxml_html.fromstring(response.content)
        return {
            'inline_script': _inline_hashes(tree, '//script[not(@src)]/text()'),
            'inline_style': _inline_hashes(tree, '//style/text()'),
            **_collect(session, page_url, _seeds(tree, page_url)),
        }
    except Exception as ex:  # pylint: disable=broad-except
        traceback.print_exc(file=sys.stdout)
        return {
            'error': str(ex).partition('. See ')[0]
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


def fetch_resource_hashes(session, url, resource_hashes, forks):
    resources = fetch_page_resources(session, url)
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
    with new_session(network_type) as session:
        for url, detail in searx_stats_result.iter_instances(only_valid=True, network_type=network_type):
            resources = fetch_resource_hashes(session, url, resource_hashes, searx_stats_result.forks)
            resources.setdefault('error', None)
            # temporary storage
            detail['html'] = {
                'resources': resources
            }
            # output progress
            external_js = len(resources.get('script', []))
            inline_js = len(resources.get('inline_script', []))
            error_msg = (resources.get('error') or '').strip()
            print('🔗 {0:60} {1:3} loaded js {2:3} inline js  {3}'.format(url, external_js, inline_js, error_msg))


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
