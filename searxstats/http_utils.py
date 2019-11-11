import sys
import socket
import ssl
import asyncio

import h11._util
import httpx
import httpx.decoders
import httpx.exceptions

from searxstats.utils import exception_to_str

if not sys.version_info.major == 3 and sys.version_info.minor >= 7:
    from contextlib import asynccontextmanager  # pylint: disable=no-name-in-module
else:
    from searxstats.backport import asynccontextmanager


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
