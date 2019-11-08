import asyncio

from searxstats.utils import new_session, exception_to_str, get_host
from searxstats.memoize import MemoizeToDisk


# FIXME: fetch old report
REFRESH_API_ENDPOINT = 'https://tls.imirhil.fr/https/{0}/refresh'
API_ENDPOINT = 'https://tls.imirhil.fr/https/{0}.json'
USER_ENDPOINT = 'https://tls.imirhil.fr/https/{0}'
TIMEOUT = 5
MAX_RETRY = 10
TIME_BETWEEN_RETRY = 6


@MemoizeToDisk()
async def analyze(host):
    refresh_url = REFRESH_API_ENDPOINT.format(host)
    api_url = API_ENDPOINT.format(host)
    user_url = USER_ENDPOINT.format(host)
    remaining_tries = MAX_RETRY
    success = False
    try:
        # 2 seconds pause between refreshs
        await asyncio.sleep(2)
        #
        async with new_session() as session:
            response = await session.get(refresh_url, timeout=TIMEOUT)
            await asyncio.sleep(1)
            while not success and remaining_tries > 0:
                response = await session.get(api_url, timeout=TIMEOUT)
                json = response.json()
                if json['pending']:
                    remaining_tries = remaining_tries - 1
                    await asyncio.sleep(TIME_BETWEEN_RETRY)
                else:
                    success = True
    except Exception as ex:
        print(host, exception_to_str(ex))
        success = False

    if success:
        # get the grades from the different IPs
        hosts = json.get('result', {}).get('hosts', [])
        ranks = list(
            set(map(lambda r: r.get('grade', {}).get('rank', '?'), hosts)))
        # concat all grade in one line, worse grade at first
        ranks.sort(reverse=True)
        ranks = ', '.join(ranks)
        #
        return (ranks, user_url)
    else:
        return ('', user_url)


async def fetch(searx_json):
    instance_details = searx_json['instances']
    for url in instance_details:
        if instance_details[url].get('version') is not None:
            if 'tls' not in instance_details[url]:
                instance_details[url]['tls'] = {}
            instance_host = get_host(url)
            instance_details[url]['tls']['grade'], instance_details[url]['tls']['gradeUrl'] =\
                await analyze(instance_host)
            print('\n🔒 {0:30} {1}'.format(instance_host, instance_details[url]['tls']['grade']))
    return True
