from lxml import etree

from searxstats.config import DEFAULT_HEADERS, DEFAULT_COOKIES
from searxstats.common.html import html_fromstring, stringify_children
from searxstats.common.http import get_host, new_session


INSTANCES_XPATH = etree.XPath(
    "//div[@class='markdown-body']//ul/li/a[@rel='nofollow']")
MARKDOWN_ELEMENTS_XPATH = etree.XPath("//div[@class='markdown-body']")
SEARX_INSTANCES_URL = 'https://github.com/asciimoo/searx/wiki/Searx-instances'
REMOVE_BEFORE_LOWER_CASE = 'list of public searx instances'


async def get_instance_urls():
    instance_urls = []

    # fetch html page
    async with new_session() as session:
        response = await session.get(SEARX_INSTANCES_URL,
                                     headers=DEFAULT_HEADERS, cookies=DEFAULT_COOKIES, timeout=10)
    html = await html_fromstring(response.text)
    # remove content before MARKDOWN_ELEMENTS_XPATH
    for element in MARKDOWN_ELEMENTS_XPATH(html)[0].getchildren():
        text = stringify_children(element)
        if text.lower().find(REMOVE_BEFORE_LOWER_CASE) >= 0:
            break
        element.clear()
    # check all links
    for aelement in INSTANCES_XPATH(html):
        ahref = aelement.get('href')
        if ahref.startswith('https://www.ssllabs.com/') or \
           ahref.startswith('https://hstspreload.org/') or \
           ahref.startswith('https://geti2p.net/') or \
           ahref.endswith('/cert/'):
            continue
        if ahref.endswith('/'):
            ahref = ahref[:-1]
        if ahref.endswith('/search'):
            ahref = ahref[:-7]
        # Remove .i2p (keep .onion URL)
        host = get_host(ahref)
        if host.endswith('.i2p'):
            continue
        ahref = ahref + '/'
        instance_urls.append(ahref)

    # remove duplicates
    instance_urls = list(set(instance_urls))

    # sort list
    instance_urls.sort()

    #
    return instance_urls
