import asyncio
from urllib.parse import urlparse
import re
import httpx
from . import model

SEARX_INSTANCES_URL = 'https://raw.githubusercontent.com/asciimoo/searx/master/docs/user/public_instances.rst'
AFTER_ALIVE_AND_RUNNING = re.compile('Alive and running(.*)Running with an incorrect SSL certificate', re.MULTILINE | re.DOTALL)
INCORRECT_SSL = re.compile('Running with an incorrect SSL certificate(.*)Offline', re.MULTILINE | re.DOTALL)
OFFLINE = re.compile('Offline(.*)', re.MULTILINE | re.DOTALL)
ITEM_RE = r'\* (.+)'
LINK_RE = r'`([^<]+)<([^>]+)>`__'

COMMENT_BLANK_TEXT = [
    'Issuer: Comodo CA Limited',
    'Issuer: Let\'s Encrypt',
    'Issuer: Lets Encrypt',
    'Issuer: LetsEncrypt',
    'Issuer: Cloudflare',
    'Issuer: StartCom',
    'Issuer: WoSign',
    'Issuer: COMODO',
    'Issuer: COMODO via GANDI',
    'Issuer: CAcert',
    'Let\'s Encrypt'
    '-',
    '(as )',
    '(as  or )',
    '(as )',
    '(as  or )',
    '(down)',
    '()',
]


def get_host(instance):
    parsed_url = urlparse(instance)
    return parsed_url.hostname


def normalize_url(url):
    if url.startswith('https://www.ssllabs.com/') or \
       url.startswith('https://hstspreload.org/') or \
       url.startswith('https://geti2p.net'):
        return None
    if url.endswith('/'):
        url = url[:-1]
    if url.endswith('/search'):
        url = url[:-7]
    return url


def get_instance_comment(line):
    instance_comment = re.sub(LINK_RE, '', line).strip()
    for _ in range(5):
        for t_blank in COMMENT_BLANK_TEXT:
            instance_comment = instance_comment.replace(t_blank, "")
        instance_comment = instance_comment.strip()
        if instance_comment.startswith('-'):
            instance_comment = instance_comment[2:].strip()
        if instance_comment.endswith('-'):
            instance_comment = instance_comment[:-1].strip()
    if instance_comment == '':
        return None
    return instance_comment


def get_instance_comments(section_comment, instance_comment):
    comments = []
    if section_comment is not None:
        comments.append(section_comment)
    if instance_comment is not None:
        comments.append(instance_comment)
    return comments

async def import_instance(instance_list, text, section_comment):
    #
    # for each item of a list
    lines = re.findall(ITEM_RE, text)
    for line in lines:
        main_url = None
        aurls = model.AdditionalUrlList()
        instance_comments = get_instance_comments(section_comment, get_instance_comment(line))
        # for each link
        links = re.findall(LINK_RE, line)
        for link in links:
            # normalize the link
            url = normalize_url(link[1])
            label = link[0].strip()
            if main_url is None:
                main_url = url
            elif url:   
                # add it
                aurls[url] = label
        #
        if main_url in instance_list:
            del instance_list[main_url]
            print('duplicate found ', main_url)
        instance_list[main_url] = model.Instance(False, instance_comments, aurls)



async def import_instance_urls():
    instance_list = model.InstanceList()

    # fetch the .rst source
    async with httpx.AsyncClient() as client:
        response = await client.get(SEARX_INSTANCES_URL, timeout=10)

    # 'Alive and running'
    match = re.search(AFTER_ALIVE_AND_RUNNING, response.text)
    if match:
        await import_instance(instance_list, match.group(0), None)

    # 'Alive and running'
    match = re.search(INCORRECT_SSL, response.text)
    if match:
        await import_instance(instance_list, match.group(0), 'Running with an incorrect SSL certificate')

    # 'Offline'
    match = re.search(OFFLINE, response.text)
    if match:
        await import_instance(instance_list, match.group(0), 'Offline')

    model.save('instances.yaml', instance_list)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(import_instance_urls())
