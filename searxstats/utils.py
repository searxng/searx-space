import socket
import ssl
import asyncio
import concurrent.futures
import sys
from urllib.parse import urlparse
import h11._util
import httpx
import httpx.exceptions
from lxml import html
from lxml.etree import _ElementStringResult, _ElementUnicodeResult  # pylint: disable=no-name-in-module
from searxstats.memoize import Memoize

if not sys.version_info.major == 3 and sys.version_info.minor >= 7:
    from contextlib import asynccontextmanager  # pylint: disable=no-name-in-module
else:
    from searxstats.backport import asynccontextmanager


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


@asynccontextmanager
async def new_session(*args, **kwargs):
    """
    Create a new httpx.AsyncClient

    No HTTP/2 because h2 doesn't work with some instances
    """
    kwargs['http_versions'] = "HTTP/1.1"
    async with httpx.AsyncClient(*args, **kwargs) as session:
        yield session


async def do_get(session, *args, **kwargs):
    """
    response, error = session.get(*args, **kwargs)

    error is user friendly, or None is there is no error.

    Doesn't trigger an exception.

    No brotlipy because of httpx.exceptions.DecodingError
    """
    response = None
    error = None
    try:
        response = await session.get(*args, **kwargs)
    except ConnectionRefusedError:
        error = 'Connection refused'
    except (httpx.exceptions.ConnectTimeout, asyncio.TimeoutError):
        error = 'Connection timed out'
    except httpx.exceptions.ReadTimeout:
        error = 'Read timeout'
    except httpx.exceptions.DecodingError:
        error = 'Decoding error'
    except httpx.exceptions.RedirectLoop:
        error = 'Redirect loop error'
    except (h11._util.RemoteProtocolError,  # pylint: disable=protected-access
            socket.gaierror, ssl.SSLError, ssl.CertificateError, OSError) as ex:
        error = exception_to_str(ex)
    except Exception as ex:
        error = 'Exception ' + str(type(ex)) + ' ' + str(ex)
    else:
        if response.status_code != 200:
            error = 'HTTP status code ' + str(response.status_code)
    return response, error
