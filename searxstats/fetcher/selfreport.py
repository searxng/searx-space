import json
from urllib.parse import urljoin
from searxstats.utils import new_session, do_get


async def get_usable_engines(session, instance_url):
    print('💡', end='', flush=True)
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


async def fetch(searx_json):
    instance_details = searx_json['instances']
    async with new_session() as session:
        for url in instance_details:
            if instance_details[url].get('version') is not None:
                instance_details[url]['status'] = await get_usable_engines(session, url)
