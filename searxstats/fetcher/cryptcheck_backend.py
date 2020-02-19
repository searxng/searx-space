# pylint: disable=invalid-name
from searxstats.common.utils import exception_to_str
from searxstats.common.http import new_client, get_host, NetworkType
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import create_fetch
from searxstats.config import CRYPTCHECK_BACKEND


API_ENDPOINT = CRYPTCHECK_BACKEND + '/https/{0}.json'
USER_ENDPOINT = 'https://cryptcheck.fr/https/{0}'
HTTP_REQUEST_TIMEOUT = 600
CACHE_EXPIRE_TIME = 24*3600


async def get_existing_result(session, host):
    """
    Return result, pending

    result is the existing result if not too told otherwise None

    pending is True if the next result is pending
    """
    api_url = API_ENDPOINT.format(host)
    response = await session.get(api_url, timeout=HTTP_REQUEST_TIMEOUT)
    if response.status_code != 200:
        return None
    return response.json()


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
            json = await get_existing_result(session, host)

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


fetch = create_fetch(['tls'], fetch_one, valid_or_private=True, network_type=NetworkType.NORMAL, limit=2)
