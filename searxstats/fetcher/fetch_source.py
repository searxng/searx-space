from urllib.parse import urlparse

from searxstats.common.utils import exception_to_str
from searxstats.data import fetch_hashes_from_url
from searxstats.model import SearxStatisticsResult
from searxstats.config import FORKS


def normalize_git_url(git_url):
    try:
        parsed_git_url = urlparse(git_url, scheme='https')
        parsed_git_url = parsed_git_url._replace(query='', fragment='')
    except Exception:
        return None
    else:
        if parsed_git_url.scheme != 'https':
            return None
        return parsed_git_url.geturl()


def iter_git_urls(searx_stats_result: SearxStatisticsResult):
    for git_url in FORKS:
        yield git_url
    for _, detail in searx_stats_result.iter_instances(only_valid=True):
        git_url = normalize_git_url(detail['git_url'])
        if git_url:
            yield git_url


# pylint: disable=unsubscriptable-object, unsupported-delete-operation, unsupported-assignment-operation
# pylint thinks that ressource_desc is None
async def fetch(searx_stats_result: SearxStatisticsResult):
    seen_git_url = set()
    for git_url in iter_git_urls(searx_stats_result):
        if git_url not in seen_git_url:
            try:
                await fetch_hashes_from_url(git_url)
            except Exception as ex:
                print(exception_to_str(ex))
            else:
                if git_url not in searx_stats_result.forks:
                    searx_stats_result.forks.append(git_url)
            seen_git_url.add(git_url)
