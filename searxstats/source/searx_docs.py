import re

from searxstats.common.http import new_client, get_host


SEARX_INSTANCES_URL = 'https://raw.githubusercontent.com/asciimoo/searx/master/docs/user/public_instances.rst'
AFTER_ALIVE_AND_RUNNING = re.compile('Alive and running(.*)', re.MULTILINE | re.DOTALL)
ITEM_RE = r'\* (.+)'
LINK_RE = r'`([^\ ]+) <([^\>]+)>`'


def normalize_url(url):
    if url.startswith('https://www.ssllabs.com/') or \
        url.startswith('https://hstspreload.org/') or \
        url.startswith('https://geti2p.net/') or \
        url.endswith('/cert/'):
        return False
    if url.endswith('/'):
        url = url[:-1]
    if url.endswith('/search'):
        url = url[:-7]
    # Remove .i2p (keep .onion URL)
    host = get_host(url)
    if host.endswith('.i2p'):
        return False
    url = url + '/'
    return url


async def get_instance_urls():
    instance_urls = []

    # fetch the .rst source
    async with new_client() as session:
        response = await session.get(SEARX_INSTANCES_URL, timeout=10)
    match = re.search(AFTER_ALIVE_AND_RUNNING, response.text)
    if match:
        lines = re.findall(ITEM_RE, match.group(0))
        if len(lines) > 0:
            for line in lines:
                links = re.findall(LINK_RE, line)
                for link in links:
                    url = normalize_url(link[1])
                    if url:
                        instance_urls.append(url)

    # remove duplicates
    instance_urls = list(set(instance_urls))

    # sort list
    instance_urls.sort()

    #
    return instance_urls
