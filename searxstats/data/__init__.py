from .query import get_fork_list, get_repositories_for_content_sha, is_wellknown_content_sha

from searxstats.config import DEBIAN_GIT_URL, DEBIAN_SOURCE_PACKAGE_NAMES
from searxstats.data.fetch_git import fetch_hashes_from_git_url
from searxstats.data.fetch_deb_hashes import fetch_hashes_from_deb_source_list


__all__ = [
    'get_fork_list',
    'get_repositories_for_content_sha',
    'is_wellknown_content_sha',
    'fetch_hashes_from_url',
    'fetch_hashes_from_git_url',
    'fetch_hashes_from_deb_source_list',
]


async def fetch_hashes_from_url(url):
    if url == DEBIAN_GIT_URL:
        return await fetch_hashes_from_deb_source_list(DEBIAN_GIT_URL, DEBIAN_SOURCE_PACKAGE_NAMES)
    fetch_hashes_from_git_url(url)
