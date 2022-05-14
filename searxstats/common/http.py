import sys
import ssl
import asyncio
import logging
from urllib.parse import urlparse
from enum import Enum

import httpx

from .utils import exception_to_str
from .memoize import Memoize
from .ssl_info import SSL_CONTEXT
from ..config import TOR_SOCKS_PROXY_HOST, TOR_SOCKS_PROXY_PORT

if not sys.version_info.major == 3 and sys.version_info.minor >= 7:
    from contextlib import asynccontextmanager  # pylint: disable=no-name-in-module
else:
    from .contextlib import asynccontextmanager


class NetworkType(Enum):
    NORMAL = 0
    TOR = 1


NETWORK_PROXIES = {
    NetworkType.TOR: httpx.Proxy(
        url=f'socks5://{TOR_SOCKS_PROXY_HOST}:{TOR_SOCKS_PROXY_PORT}')
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
async def new_client(*args, **kwargs):
    """
    Create a new httpx.AsyncClient
    """
    network_type = NetworkType.NORMAL
    if 'network_type' in kwargs:
        if kwargs['network_type']:
            network_type = kwargs['network_type']
            kwargs['proxies'] = NETWORK_PROXIES.get(network_type, None)
        del kwargs['network_type']
    async with httpx.AsyncClient(*args, **kwargs, verify=SSL_CONTEXT, http2=True, follow_redirects=True) as session:
        session._network_type = network_type  # pylint: disable=protected-access
        yield session


async def _request_unsafe(*args, **kwargs):
    try:
        async with new_client(verify=False) as unsafe_session:
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

    See the `initialize` function
    """
    response = None
    error = None
    try:
        response = await method(*args, **kwargs)
    except httpx.ConnectTimeout:
        error = 'Connection timed out'
    except asyncio.TimeoutError:
        error = 'Connection timed out (asyncio)'
    except httpx.ReadTimeout:
        error = 'Read timeout'
    except httpx.DecodingError:
        error = 'Decoding error'
    except httpx.TooManyRedirects:
        error = 'Redirect loop error'
    except httpx.ProtocolError:
        error = 'Protocol error'
    except httpx.NetworkError as ex:
        # args[0] is the wrapped exception
        wrapped_ex = ex.args[0]
        if isinstance(wrapped_ex, ConnectionRefusedError):
            error = 'Connection refused'
        else:  # socket.gaierror, ssl.SSLError, h11._util.RemoteProtocolError
            error = exception_to_str(wrapped_ex)
    except httpx.ProxyError as ex:
        print(ex)
        error = exception_to_str(ex)
        session = getattr(method, '__self__', None)
        network_type = NetworkType.NORMAL
        if session is not None:
            network_type = getattr(
                session, '_network_type', NetworkType.NORMAL)
        if network_type == NetworkType.TOR:
            error = 'Tor Error'
    except ssl.CertificateError as ex:
        if kwargs.get('verify', True):
            # get the certficate even if it is not validated.
            response = await _request_unsafe(*args, **kwargs)
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


# pylint: disable=global-variable-undefined, invalid-name
async def initialize():
    """
    do the equivalent of
    ```
    @UseQueue(count=1, loop=loop)
    async def request(method, *args, **kwargs):
        ...
    ```
    once the `loop` value is known
    """
    for logger_name in ('hpack.hpack', 'hpack.table', 'httpx._client'):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
