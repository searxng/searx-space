import sys
import socket
import ssl
import asyncio
from urllib.parse import urlparse
from enum import Enum

import h11._util
import httpx
import httpx.decoders
import httpx.exceptions

from .utils import exception_to_str
from .queuecalls import UseQueue
from .memoize import Memoize
from ..config import TOR_HTTP_PROXY

if not sys.version_info.major == 3 and sys.version_info.minor >= 7:
    from contextlib import asynccontextmanager  # pylint: disable=no-name-in-module
else:
    from .contextlib import asynccontextmanager


class NetworkType(Enum):
    NORMAL = 0
    TOR = 1


NETWORK_PROXIES = {
    NetworkType.TOR: httpx.HTTPProxy(
        proxy_url=TOR_HTTP_PROXY,
        proxy_mode="TUNNEL_ONLY"  # Tor is a tunnel only proxy
    )
}

TOR_PROXY_ERROR = {
    403: "Forbidden (connection refused|exit policy|connection reset|entry policy violation)",
    404: "Not Found (resolve failed|no route)",
    500: "Internal Server Error",
    502: "Bad Gateway (destroy cell received|unexpected close|hibernating server|internal error"
         + "|resource limit|tor protocol violation)",
    504: "Gateway Timeout",
}


@Memoize(None)
def get_host(instance):
    parsed_url = urlparse(instance)
    return parsed_url.hostname


def get_network_type(url):
    if get_host(url).endswith('.onion'):
        return NetworkType.TOR
    return NetworkType.NORMAL


@asynccontextmanager
async def new_session(*args, **kwargs):
    """
    Create a new httpx.AsyncClient
    """
    network_type = NetworkType.NORMAL
    if 'network_type' in kwargs:
        if kwargs['network_type']:
            network_type = kwargs['network_type']
            kwargs['proxies'] = NETWORK_PROXIES.get(network_type, None)
        del kwargs['network_type']
    async with httpx.Client(*args, **kwargs) as session:
        session._network_type = network_type  # pylint: disable=protected-access
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


# pylint: disable=too-many-branches
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
    except httpx.exceptions.ProxyError as ex:
        error = exception_to_str(ex)
        session = getattr(method, '__self__', None)
        network_type = NetworkType.NORMAL
        if session is not None:
            network_type = getattr(session, '_network_type', NetworkType.NORMAL)
        if ex.response and network_type == NetworkType.TOR:
            error = 'Tor Error: ' + TOR_PROXY_ERROR.get(ex.response.status_code, error)
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
