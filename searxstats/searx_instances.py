from searxstats.config import get_searxinstances_repository_directory, SEARXINSTANCES_GIT_REPOSITORY
from searxstats.model import SearxStatisticsResult
from searxstats.common.git_tool import get_repository
from searxstats.common.utils import import_module


def load_searx_instances() -> dict:
    repo_directory = get_searxinstances_repository_directory()
    get_repository(repo_directory, SEARXINSTANCES_GIT_REPOSITORY)
    model_module = import_module('searxinstances.model', repo_directory)
    return model_module.load()


def add_slash(url: str) -> str:
    if not url.endswith('/'):
        return url + '/'
    else:
        return url


async def get_searx_stats_result() -> SearxStatisticsResult:
    searx_stats_result = SearxStatisticsResult()
    searx_instances = load_searx_instances()
    for url, instance in searx_instances.items():
        url = add_slash(url)
        searx_stats_result.update_instance(url, {
            'comments': instance.comments,
            'alternativeUrls': instance.additional_urls
        })
        for aurl, comment in instance.additional_urls.items():
            aurl = add_slash(aurl)
            aurls_for_aurl = dict()
            for ourl, ocomment in instance.additional_urls.items():
                if ourl != aurl:
                    aurls_for_aurl[add_slash(ourl)] = ocomment
            aurls_for_aurl[url] = ''

            searx_stats_result.update_instance(aurl, {
                'comments': [comment],
                'alternativeUrls': aurls_for_aurl,
            })

    return searx_stats_result


async def get_searx_stats_result_from_list(instance_urls: list) -> SearxStatisticsResult:
    searx_stats_result = SearxStatisticsResult()
    for url in instance_urls:
        url = add_slash(url)
        searx_stats_result.update_instance(url, {
            'comments': [],
            'alternativeUrls': dict()
        })
    return searx_stats_result
