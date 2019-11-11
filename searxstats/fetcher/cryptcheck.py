import asyncio
import time
import datetime

from searxstats.utils import exception_to_str, get_host
from searxstats.http_utils import new_session
from searxstats.memoize import MemoizeToDisk
from searxstats.model import SearxStatisticsResult


REFRESH_API_ENDPOINT = 'https://tls.imirhil.fr/https/{0}/refresh'
API_ENDPOINT = 'https://tls.imirhil.fr/https/{0}.json'
USER_ENDPOINT = 'https://tls.imirhil.fr/https/{0}'
TIMEOUT = 5
MAX_RETRY = 12
TIME_BETWEEN_RETRY = 5
CACHE_EXPIRE_TIME = 24*3600


async def get_existing_result(session, host, expire_time):
    """
    Return result, pending

    result is the existing result if not too told otherwise None

    pending is True if the next result is pending
    """
    api_url = API_ENDPOINT.format(host)
    response = await session.get(api_url, timeout=TIMEOUT)
    json = response.json()
    pending = json.get('pending', False)
    result = None
    if pending:
        updated = json.get('updated_at', None)
        updated_dt = datetime.datetime.strptime(updated, '%Y-%m-%dT%H:%M:%S.%fZ')
        updated_ts = updated_dt.timestamp()
        if time.time() - updated_ts <= expire_time:
            result = json
    return result, pending


async def refresh_result(session, host):
    refresh_url = REFRESH_API_ENDPOINT.format(host)
    await session.get(refresh_url, timeout=TIMEOUT)
    await asyncio.sleep(5)


async def pool_result(session, host):
    api_url = API_ENDPOINT.format(host)
    remaining_tries = MAX_RETRY
    result = None
    while result is None and remaining_tries > 0:
        response = await session.get(api_url, timeout=TIMEOUT)
        json = response.json()
        if json['pending']:
            remaining_tries = remaining_tries - 1
            await asyncio.sleep(TIME_BETWEEN_RETRY)
        else:
            result = json
    return result


def validate_result(result):
    if isinstance(result, tuple):
        return result[0] != '' and result[0] is not None
    return True


@MemoizeToDisk(validate_result=validate_result, expire_time=CACHE_EXPIRE_TIME)
async def analyze(host):
    user_url = USER_ENDPOINT.format(host)
    json = None
    try:
        async with new_session() as session:
            json, pending = await get_existing_result(session, host, CACHE_EXPIRE_TIME)
            if json is None:
                # no existing result or too old
                if not pending:
                    # ask for refresh
                    await refresh_result(session, host)
                # pool the response
                json = await pool_result(session, host)
    except Exception as ex:
        print(host, exception_to_str(ex))

    try:
        if json is not None and json.get('result') is not None:
            # get the grades from the different IPs
            hosts = json['result'].get('hosts', [])
            ranks = list(
                set(map(lambda r: r.get('grade', {}).get('rank', '?'), hosts)))
            # concat all grade in one line, worse grade at first
            ranks.sort(reverse=True)
            ranks = ', '.join(ranks)
            #
            return (ranks, user_url)
        else:
            return ('', user_url)
    except Exception as ex:
        print(host, exception_to_str(ex))
        return ('', user_url)


async def fetch(searx_stats_result: SearxStatisticsResult):
    for url, detail in searx_stats_result.iter_valid_instances():
        if 'tls' not in detail:
            detail['tls'] = {}
        instance_host = get_host(url)
        detail['tls']['grade'], detail['tls']['gradeUrl'] = await analyze(instance_host)
        print('🔒 {0:30} {1}'.format(instance_host, detail['tls']['grade']))
    return True
