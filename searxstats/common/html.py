import asyncio
import concurrent.futures

from itertools import chain
from lxml import etree, html
from lxml.etree import _ElementStringResult, _ElementUnicodeResult  # pylint: disable=no-name-in-module

FROMSTRING_THREADPOOL = concurrent.futures.ThreadPoolExecutor(max_workers=8)


for i in range(0, 8):
    FROMSTRING_THREADPOOL.submit(lambda: None)


async def html_fromstring(content, *args):
    if len(content) < 128:
        return html.fromstring(content, *args)
    else:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(FROMSTRING_THREADPOOL, html.fromstring, content, *args)


def extract_text(xpath_results):
    if isinstance(xpath_results, list):
        # it's list of result : concat everything using recursive call
        result = ''
        for element in xpath_results:
            result = result + extract_text(element)
        return result.strip()
    elif isinstance(xpath_results, (_ElementStringResult, _ElementUnicodeResult)):
        # it's a string
        return ''.join(xpath_results)
    else:
        # it's a element
        text = html.tostring(
            xpath_results, encoding='unicode', method='text', with_tail=False
        )
        text = text.strip().replace('\n', ' ')
        return ' '.join(text.split())


def stringify_children(node):
    parts = ([node.text] +
             list(chain(*([c.text, str(etree.tostring(c)), c.tail] for c in node.getchildren()))) +
             [node.tail])
    # filter removes possible Nones in texts and tails
    return ''.join(filter(None, parts))
