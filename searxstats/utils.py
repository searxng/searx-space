import traceback
import inspect
import asyncio
import concurrent.futures
import sys
from urllib.parse import urlparse
from lxml import html
from lxml.etree import _ElementStringResult, _ElementUnicodeResult  # pylint: disable=no-name-in-module
from searxstats.memoize import Memoize


THREADPOOL = concurrent.futures.ThreadPoolExecutor(max_workers=8)


for i in range(0, 8):
    THREADPOOL.submit(lambda: None)


async def html_fromstring(content, *args):
    if len(content) < 128:
        return html.fromstring(content, *args)
    else:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(THREADPOOL, html.fromstring, content, *args)


@Memoize(None)
def get_host(instance):
    parsed_url = urlparse(instance)
    return parsed_url.hostname


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


ERROR_REMOVE_PREFIX = "[SSL: CERTIFICATE_VERIFY_FAILED] "


def exception_to_str(ex):
    result = str(ex)
    if result == '':
        result = str(type(ex))
    elif result.startswith(ERROR_REMOVE_PREFIX):
        result = result[len(ERROR_REMOVE_PREFIX):]
    return result


def safe_func(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception:
        traceback.print_exc(file=sys.stdout)


async def safe_async_func(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except Exception:
        traceback.print_exc(file=sys.stdout)


def create_task(loop, function, *args, **kwargs):
    if inspect.iscoroutinefunction(function):
        # async task in the loop
        return loop.create_task(safe_async_func(function, *args, **kwargs))
    else:
        # run sync tasks in a thread pool
        return loop.run_in_executor(None, safe_func, function, *args, **kwargs)
