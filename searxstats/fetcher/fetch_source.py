from urllib.parse import urlparse

from searxstats.config import SEARX_GIT_REPOSITORY
from searxstats.data.well_kown_hashes import fetch_file_content_hashes
from searxstats.model import SearxStatisticsResult


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


# pylint: disable=unsubscriptable-object, unsupported-delete-operation, unsupported-assignment-operation
# pylint thinks that ressource_desc is None
def fetch(searx_stats_result: SearxStatisticsResult):
    seen_git_url = set()
    for _, detail in searx_stats_result.iter_instances(only_valid=True):
        git_url = detail.get('git_url', SEARX_GIT_REPOSITORY)
        git_url = normalize_git_url(git_url)
        if git_url and git_url not in seen_git_url:
            try:
                fetch_file_content_hashes(git_url)
            except Exception:
                pass
            else:
                if git_url not in searx_stats_result.forks:
                    searx_stats_result.forks.append(git_url)
            seen_git_url.add(git_url)
