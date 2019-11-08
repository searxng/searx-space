import asyncio
from searxstats.utils import new_session, exception_to_str, get_host
from searxstats.memoize import MemoizeToDisk

# see https://github.com/ssllabs/ssllabs-scan/blob/master/ssllabs-api-docs-v3.md
# API: https://github.com/mozilla/http-observatory/blob/master/httpobs/docs/api.md

API_ENDPOINT = 'https://http-observatory.security.mozilla.org/api/v1/'
API_NEW = API_ENDPOINT + 'analyze?host={0}&third-party=0'
API_GET = API_ENDPOINT + 'analyze?host={0}'
API_DETAIL = API_ENDPOINT + 'getScanResults?scan={1}'
USER_ENDPOINT = 'https://observatory.mozilla.org/analyze/{0}'
MAX_RETRY = 6
TIME_BETWEEN_RETRY = 10


@MemoizeToDisk()
async def analyze(host):
    print('\n📄 ' + host, end='')
    user_url = USER_ENDPOINT.format(host)
    try:
        async with new_session() as session:
            response = await session.post(API_NEW.format(host))
            json = response.json()
            if json.get('error') == 'rescan-attempt-too-soon':
                return False

            finished = False
            grade = None
            remaining_tries = MAX_RETRY
            while not finished:
                await asyncio.sleep(TIME_BETWEEN_RETRY)
                print('.', end='', flush=True)
                response = await session.get(API_GET.format(host), timeout=5)
                json = response.json()
                state = json.get('state', '')
                if state == 'FINISHED':
                    finished = True
                    grade = json.get('grade')
                elif state in ['ABORTED', 'FAILED']:
                    finished = True
                    grade = None
                elif state not in ['PENDING', 'STARTING', 'RUNNING']:
                    print(host, 'unknow state ', state)
                    finished = True
                    grade = None
                #
                if remaining_tries == 0:
                    finished = True
                    grade = None
                else:
                    remaining_tries = remaining_tries - 1
    except Exception as ex:
        print(host, exception_to_str(ex))
        grade = None
    return (grade, user_url)


async def fetch(searx_json):
    instance_details = searx_json['instances']
    for url in instance_details:
        if instance_details[url].get('version') is not None:
            if 'http' not in instance_details[url]:
                instance_details[url]['http'] = {}
            instance_details[url]['http']['grade'], instance_details[url]['http']['gradeUrl'] =\
                await analyze(get_host(url))
    return True
