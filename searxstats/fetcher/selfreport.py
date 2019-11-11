import json
from urllib.parse import urljoin
from searxstats.http_utils import new_session, do_get
from searxstats.memoize import MemoizeToDisk
from searxstats.model import SearxStatisticsResult


# # pylint: disable=unused-argument
def get_usable_engines_key(_, instance_url):
    return instance_url


@MemoizeToDisk(func_key=get_usable_engines_key)
async def get_usable_engines(session, instance_url):
    result = None
    response, error = await do_get(session, urljoin(instance_url, 'status'), timeout=5)
    if response is not None and error is None and response.status_code == 200:
        result = []
        try:
            status_json = response.json()
        except json.JSONDecodeError:
            pass
        else:
            engine_status_dict = status_json.get('engines_state', {})
            for name, detail in engine_status_dict.items():
                if detail.get('status'):
                    result.append(name)
    return result


async def fetch(searx_stats_result: SearxStatisticsResult):
    async with new_session() as session:
        for url, detail in searx_stats_result.iter_valid_instances():
            detail['status'] = await get_usable_engines(session, url)
            print('💡 {0:30}'.format(url))
