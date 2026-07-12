import asyncio
import concurrent.futures

from lxml import html

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
    elif isinstance(xpath_results, str):
        # it's a string
        return ''.join(xpath_results)
    else:
        # it's a element
        text = html.tostring(
            xpath_results, encoding='unicode', method='text', with_tail=False
        )
        text = text.strip().replace('\n', ' ')
        return ' '.join(text.split())
