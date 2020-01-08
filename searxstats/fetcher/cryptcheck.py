# pylint: disable=invalid-name
import asyncio
import time
import datetime

from searxstats.common.utils import exception_to_str
from searxstats.common.http import new_client, get_host, NetworkType
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import create_fetch

# Alternative solution: use https://github.com/aeris/cryptcheck and run
# docker run --rm aeris22/cryptcheck https <hostname> -qj --no-ipv6

BASE_URL = 'https://cryptcheck.fr/https/'
REFRESH_API_ENDPOINT = BASE_URL + '{0}/refresh'
API_ENDPOINT = BASE_URL + '{0}.json'
USER_ENDPOINT = BASE_URL + '{0}'
HTTP_REQUEST_TIMEOUT = 5
# searx-stats wait for cryptcheck
# timeout = MAX_RETRY * TIME_BETWEEN_RETRY = 18*10 = 180 seconds = 3 minutes
MAX_RETRY = 18
TIME_BETWEEN_RETRY = 10
CACHE_EXPIRE_TIME = 24*3600


async def get_existing_result(session, host, expire_time):
    """
    Return result, pending

    result is the existing result if not too told otherwise None

    pending is True if the next result is pending
    """
    api_url = API_ENDPOINT.format(host)
    response = await session.get(api_url, timeout=HTTP_REQUEST_TIMEOUT)
    json = response.json()
    pending = json.get('pending', False)
    result = None
    if not pending:
        updated = json.get('updated_at', None)
        updated_dt = datetime.datetime.strptime(updated, '%Y-%m-%dT%H:%M:%S.%fZ')
        updated_ts = updated_dt.timestamp()
        if time.time() - updated_ts <= expire_time:
            result = json
    return result, pending


async def refresh_result(session, host):
    refresh_url = REFRESH_API_ENDPOINT.format(host)
    await session.get(refresh_url, timeout=HTTP_REQUEST_TIMEOUT)
    await asyncio.sleep(TIME_BETWEEN_RETRY)


async def pool_result(session, host):
    api_url = API_ENDPOINT.format(host)
    remaining_tries = MAX_RETRY
    result = None
    while result is None and remaining_tries > 0:
        response = await session.get(api_url, timeout=HTTP_REQUEST_TIMEOUT)
        json = response.json()
        if json['pending']:
            remaining_tries = remaining_tries - 1
            await asyncio.sleep(TIME_BETWEEN_RETRY)
        else:
            result = json
    return result


def validate_result(result):
    if isinstance(result, tuple):
        grade = result[0]
        return grade is not None and grade != ''
    return True


@MemoizeToDisk(validate_result=validate_result, expire_time=CACHE_EXPIRE_TIME)
async def analyze(host):
    user_url = USER_ENDPOINT.format(host)
    json = None
    try:
        # get the result from cryptcheck.fr
        async with new_client() as session:
            json, pending = await get_existing_result(session, host, CACHE_EXPIRE_TIME)
            if json is None:
                # no existing result or too old
                if not pending:
                    # ask for refresh
                    await refresh_result(session, host)
                # pool the response
                json = await pool_result(session, host)

        # get the ranks from the result
        if json is not None and json.get('result') is not None:
            # get the grades from the different IPs (use a set to remove duplicates)
            ranks = list(
                set(map(lambda r: r.get('grade', '?'), json['result'])))
            # concat all the grades in one line, worse grade in front
            ranks.sort(reverse=True)
            ranks = ', '.join(ranks)
            #
            return (ranks, user_url)
        else:
            return ('?', user_url)
    except Exception as ex:
        print(host, exception_to_str(ex))
        return ('?', user_url)


async def fetch_one(url: str) -> dict:
    instance_host = get_host(url)
    grade, grade_url = await analyze(instance_host)
    print('🔒 {0:30} {1}'.format(instance_host, grade))
    return {'grade': grade, 'gradeUrl': grade_url}


fetch = create_fetch(['tls'], fetch_one, only_valid=True, network_type=NetworkType.NORMAL, limit=2)
