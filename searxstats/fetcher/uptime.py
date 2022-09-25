# pylint: disable=invalid-name
from searxstats.common.http import get, new_client, NetworkType
from searxstats.model import SearxStatisticsResult

UPTIME_URL = 'https://raw.githubusercontent.com/searxng/searx-instances-uptime/master/history/summary.json'


def percent_str_to_float(s):
    return float(s.replace('%', ''))


# pylint: disable=unsubscriptable-object, unsupported-delete-operation, unsupported-assignment-operation
# pylint thinks that ressource_desc is None
async def fetch(searx_stats_result: SearxStatisticsResult):
    async with new_client(network_type=NetworkType.NORMAL) as session:
        response, error = await get(session, UPTIME_URL)
    if error:
        print(error)
        return
    uptime_list = response.json()
    uptimes = {}
    for instance in uptime_list:
        uptimes[instance['url'] + '/'] = {
            'uptimeDay': percent_str_to_float(instance['uptimeDay']),
            'uptimeWeek': percent_str_to_float(instance['uptimeWeek']),
            'uptimeMonth': percent_str_to_float(instance['uptimeMonth']),
            'uptimeYear': percent_str_to_float(instance['uptimeYear']),
        }

    for url, detail in searx_stats_result.iter_instances(valid_or_private=True):
        detail['uptime'] = uptimes.get(url)
