# pylint: disable=invalid-name
import httpx

from searxstats.common.utils import exception_to_str
from searxstats.common.http import get_host, NetworkType
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import create_fetch


USER_ENDPOINT = 'https://observatory.mozilla.org/analyze/{0}'


def validate_result(result):
    if isinstance(result, tuple):
        return result[0] is not None and result[0] != ''
    return True


@MemoizeToDisk(validate_result=validate_result, expire_time=24*3600)
def analyze(url: str):
    host = get_host(url)
    grade_url = USER_ENDPOINT.format(host)
    grade = None
    score = None
    try:
        response = httpx.post(
            'https://observatory-api.mdn.mozilla.net/api/v2/scan?host={0}'.format(host),
            timeout=60)
        if response.status_code == 200:
            payload = response.json()
            if not payload.get('error'):
                grade = payload.get('grade')
                score = payload.get('score')
    except Exception as ex:
        print(url, exception_to_str(ex))
    return (grade, grade_url, score)


def fetch_one(url: str) -> dict:
    grade, grade_url, score = analyze(url)
    print('📄 {0:30} {1}'.format(url, grade))
    return {'grade': grade, 'gradeUrl': grade_url, 'score': score}


fetch = create_fetch(['http'], fetch_one, valid_or_private=True, network_type=NetworkType.NORMAL, limit=4)
