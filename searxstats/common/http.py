import sys
import socket
import ssl
import asyncio
from urllib.parse import urlparse

import h11._util
import httpx
import httpx.decoders
import httpx.exceptions

from .utils import exception_to_str
from .queuecalls import UseQueue
from .memoize import Memoize

if not sys.version_info.major == 3 and sys.version_info.minor >= 7:
    from contextlib import asynccontextmanager  # pylint: disable=no-name-in-module
else:
    from .contextlib import asynccontextmanager


@Memoize(None)
def get_host(instance):
    parsed_url = urlparse(instance)
    return parsed_url.hostname


@asynccontextmanager
async def new_session(*args, **kwargs):
    """
    Create a new httpx.AsyncClient

    No HTTP/2 because h2 doesn't work with some instances
    """
    async with httpx.Client(*args, **kwargs) as session:
        yield session


def patch_request(args, kwargs):
    if get_host(args[0]) == 'searx.be':
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        headers = kwargs['headers']
        headers['Accept-Encoding'] = 'identity'


async def _request_unsafe(*args, **kwargs):
    try:
        async with new_session(verify=False) as unsafe_session:
            return await unsafe_session.get(*args, **kwargs)
    except Exception:
        pass
    return None


async def request(method, *args, **kwargs):
    """
    response, error = session.get(*args, **kwargs)

    `error` is user friendly error message, or None if there is no error.
    HTTP status code different from 200 is an error.

    Doesn't trigger an exception.
    """
    patch_request(args, kwargs)
    response = None
    error = None
    try:
        response = await method(*args, **kwargs)
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
    except (ssl.CertificateError, ssl.SSLError) as ex:
        if kwargs.get('verify', True):
            # get the certficate even if it is not validated.
            response = await _request_unsafe(*args, **kwargs)
        error = exception_to_str(ex)
    except (h11._util.RemoteProtocolError,  # pylint: disable=protected-access
            OSError, socket.gaierror) as ex:
        error = exception_to_str(ex)
    except Exception as ex:
        error = 'Exception ' + str(type(ex)) + ' ' + str(ex)
    else:
        if response.status_code != 200:
            error = 'HTTP status code ' + str(response.status_code)
    return response, error


async def get(session, *args, **kwargs):
    return await request(session.get, *args, **kwargs)


async def post(session, *args, **kwargs):
    return await request(session.post, *args, **kwargs)


def monkey_patch():
    # brotlipy is installed by selenium package
    # brotlipy causes "Decoding Error" with some instances
    # so disable brotli
    if "br" in httpx.decoders.SUPPORTED_DECODERS:
        httpx.decoders.SUPPORTED_DECODERS.pop("br")
        # pylint: disable=consider-iterating-dictionary
        httpx.decoders.ACCEPT_ENCODING = ", ".join(
            [key for key in httpx.decoders.SUPPORTED_DECODERS.keys() if key !=
             "identity"]
        )


# pylint: disable=global-variable-undefined, invalid-name
async def initialize(loop=None):
    """
    call `monkey_patch` and do the equivalent of
    ```
    @UseQueue(count=1, loop=loop)
    async def request(method, *args, **kwargs):
        ...
    ```
    once the `loop` value is known
    """
    global request
    request = UseQueue(worker_count=1, loop=loop)(request)
    monkey_patch()
