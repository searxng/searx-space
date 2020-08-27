# pylint: disable=invalid-name
from urllib.parse import urlparse
from httpobs.scanner.local import scan
from searxstats.config import DEFAULT_HEADERS
from searxstats.common.utils import exception_to_str
from searxstats.common.http import NetworkType
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import create_fetch


USER_ENDPOINT = 'https://observatory.mozilla.org/analyze/{0}'


@MemoizeToDisk()
def analyze(url: str):
    parsed_url = urlparse(url)
    grade_url = USER_ENDPOINT.format(parsed_url.hostname)
    grade = None
    try:
        result = scan(str(parsed_url.hostname), path=str(parsed_url.path), headers=DEFAULT_HEADERS)
        grade = result.get('scan', {}).get('grade', None)
    except Exception as ex:
        print(url, exception_to_str(ex))
        grade = None
    return (grade, grade_url)


def fetch_one(url: str) -> dict:
    grade, grade_url = analyze(url)
    print('📄 {0:30} {1}'.format(url, grade))
    return {'grade': grade, 'gradeUrl': grade_url}


fetch = create_fetch(['http'], fetch_one, valid_or_private=True, network_type=NetworkType.NORMAL, limit=4)
