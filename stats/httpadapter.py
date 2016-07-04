import logging
import pycurl
import certifi
import threading
from itertools import cycle
from io import BytesIO
from time import time
from concurrent.futures import ThreadPoolExecutor


# We should ignore SIGPIPE when using pycurl.NOSIGNAL - see
# the libcurl tutorial for more info.
try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
except ImportError:
    pass


def callback_get_response(response_container):
    return response_container


def get_connection():
    # pycurl initialization
    h = pycurl.Curl()

    # follow redirects
    h.setopt(pycurl.FOLLOWLOCATION, False)

    # enable compression
    h.setopt(pycurl.ENCODING, 'gzip, deflate')

    # certifi
    h.setopt(pycurl.CAINFO, certifi.where())

    # no signal
    h.setopt(pycurl.NOSIGNAL, 1)

    # certificate informations
    h.setopt(pycurl.OPT_CERTINFO, 1)

    return h


class RequestContainer(object):
    def __init__(self,
                 url,
                 curl_handler,
                 method='GET',
                 headers=None,
                 cookies=None,
                 callback=None,
                 callback_parameters=None,
                 data=None,
                 timeout=5000,
                 ssl_verification=True,
                 proxy=None
                 ):

        if headers is None:
            headers = {}

        if cookies is None:
            cookies = {}

        if callback is None:
            callback = callback_get_response

        if callback_parameters is None:
            callback_parameters = ()

        self.url = url
        self.timeout = timeout

        self.callback = callback
        self.callback_parameters = callback_parameters
        self.curl_handler = curl_handler
        self._response_buffer = BytesIO()
        self.response = None

        # curl_handler
        curl_handler.setopt(curl_handler.URL, url)

        curl_handler.setopt(curl_handler.WRITEFUNCTION, self._response_buffer.write)

        curl_handler.setopt(curl_handler.SSL_VERIFYPEER, int(ssl_verification))

        curl_handler.setopt(curl_handler.CONNECTTIMEOUT_MS, self.timeout)
        curl_handler.setopt(curl_handler.TIMEOUT_MS, self.timeout)

        curl_handler.setopt(curl_handler.HTTPHEADER,
                            ['{0}: {1}'.format(k, v)
                             for k, v in headers.items()])

        if data is not None:
            curl_handler.setopt(curl_handler.POSTFIELDS, urlencode(data))

        if proxy is not None:
            curl_handler.setopt(curl_handler.PROXY, proxy)

        if cookies:
            curl_handler.setopt(curl_handler.COOKIE, '; '.join('{0}={1}'.format(k, v)
                                for k, v in cookies.items()))
        else:
            curl_handler.unsetopt(curl_handler.COOKIE)

    def set_timeout(self, timeout):
        self.timeout = int(timeout)
        self.curl_handler.setopt(pycurl.CONNECTTIMEOUT_MS, self.timeout)
        self.curl_handler.setopt(pycurl.TIMEOUT_MS, self.timeout)

    def extract_response(self, curl_error_code=None, curl_error_message=None):
        body = self._response_buffer.getvalue()
        status_code = self.curl_handler.getinfo(pycurl.HTTP_CODE)
        content_type = self.curl_handler.getinfo(pycurl.CONTENT_TYPE)

        # timings
        timing_infos = (
            ("TOTAL_TIME", pycurl.TOTAL_TIME),
            ("NAMELOOKUP_TIME", pycurl.NAMELOOKUP_TIME),
            ("CONNECT_TIME", pycurl.CONNECT_TIME),
            ("APPCONNECT_TIME", pycurl.APPCONNECT_TIME),
            ("PRETRANSFER_TIME", pycurl.PRETRANSFER_TIME),
            ("STARTTRANSFER_TIME", pycurl.STARTTRANSFER_TIME),
            ("REDIRECT_TIME", pycurl.REDIRECT_TIME),
            ("REDIRECT_COUNT", pycurl.REDIRECT_COUNT)
        )

        timings = {}
        for i in timing_infos:
            timings[i[0]] = self.curl_handler.getinfo(i[1])

        # certinfo
        try:
            certinfo = self.curl_handler.getinfo(pycurl.INFO_CERTINFO)

            dictcertinfo = []
            for cert in certinfo:
                d = {}
                for k, v in cert:
                    d[k] = v
                dictcertinfo.append(d)
        except UnicodeDecodeError:
            # FIXME ? trigger by curl_handler.getinfo(...)
            dictcertinfo = []

        # close
        self._response_buffer.close()
        self.curl_handler.close()

        # create object
        self.response = ResponseContainer(self.url, dictcertinfo, status_code,
                                          curl_error_code, curl_error_message,
                                          body, content_type, timings)


class ResponseContainer(object):
    def __init__(self, url, certinfo, status_code, curl_error_code, curl_error_message, body, content_type, timings):
        self.url = url
        self.certinfo = certinfo
        self.status_code = status_code
        self.text = self.content = body
        self.content_type = content_type
        self.timings = timings
        self.curl_error_code = curl_error_code
        self.curl_error_message = curl_error_message

    def __str__(self):
        if self.curl_error_code is not None:
            return 'ResponseContainer<Error : ' + self.curl_error_message + ' (' + str(self.curl_error_code) + ')>'
        else:
            return 'ResponseContainer<HTTP status code:' + str(self.status_code) + '>'


class MultiRequest(object):

    def __init__(self, multi_handler=None, max_simultanous_connections=None, defer_callbacks=False):
        self.requests = {}

        if multi_handler:
            self._curl_multi_handler = multi_handler
        else:
            self._curl_multi_handler = pycurl.CurlMulti()

        if max_simultanous_connections is not None:
            self._curl_multi_handler.setopt(pycurl.M_MAX_TOTAL_CONNECTIONS, max_simultanous_connections)

        self._defer_callbacks = defer_callbacks
        self._async_callbacks = []
        self._async_results = []

    def count(self):
        return len(self.requests)

    def add(self, url, **kwargs):
        handle = get_connection()
        request_container = RequestContainer(url, handle, **kwargs)
        try:
            self._curl_multi_handler.add_handle(handle)
            self.requests[handle] = request_container
        except pycurl.error as error:
            print(error)

    def _callback(self, callback, response, *parameters):
        if self._defer_callbacks:
            self._async_callbacks.append(
                (callback,
                 response,) + parameters
            )
        else:
            self._async_results.append(POOL.submit(callback,
                                                   response,
                                                   *parameters))

    def send_requests(self):
        # no request ?
        results = []

        if len(self.requests) == 0:
            return results

        # a least one request
        select_timeout = 1.0

        # set timeout
        timeout = max(c.timeout for c in self.requests.values())
        for h, c in self.requests.items():
            c.set_timeout(timeout)

        # curl loop
        send_start = time()
        handles_num = len(self.requests)
        results = []
        while handles_num:
            # sleep until some more data is available.
            self._curl_multi_handler.select(select_timeout)

            # Run the internal curl state machine for the multi stack
            while 1:
                ret, new_handles_num = self._curl_multi_handler.perform()

                if new_handles_num < handles_num:
                    num_q, success_list, error_list = self._curl_multi_handler.info_read()
                    for h in success_list:
                        # init self.requests[h].response
                        # call in main thread to avoid conflict usage of the curl handler
                        self.requests[h].extract_response()
                        # async calling callbacks
                        self._callback(
                            self.requests[h].callback,
                            self.requests[h].response,
                            *self.requests[h].callback_parameters
                        )
                    for h, error_code, error_message in error_list:
                        self.requests[h].extract_response(curl_error_code=error_code, curl_error_message=error_message)
                        self._callback(
                            self.requests[h].callback,
                            self.requests[h].response,
                            *self.requests[h].callback_parameters
                        )

                    handles_num -= len(success_list) + len(error_list)

                if ret != pycurl.E_CALL_MULTI_PERFORM:
                    break

        self._curl_multi_handler.close()

        for async_call in self._async_callbacks:
            self._async_results.append(POOL.submit(*async_call))

        for future in self._async_results:
            remaining_time = max(0.0, timeout - (time() - send_start))
            try:
                results.append(future.result(timeout=remaining_time))
            except TimeoutError:
                logging.warning('engine timeout: {0}'.format(th._engine_name))

        return results


def fetch(url, **kwargs):
    handle = get_connection()
    request_container = RequestContainer(url, handle, **kwargs)
    try:
        handle.perform()
        request_container.extract_response()
    except pycurl.error as error:
        error_code, error_message = error.args[0], error.args[1]
        request_container.extract_response(curl_error_code=error_code, curl_error_message=error_message)
    return request_container.response


# Thread pool with the GIL limitation
POOL = ThreadPoolExecutor(8)

if __name__ == '__main__':

    def __test_callback(responseContainer):
        print(responseContainer.url, responseContainer.content_type, responseContainer.status_code, responseContainer.curl_error_code, )

    r = MultiRequest(defer_callbacks=False, max_simultanous_connections=None)
    useragent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36'
    r.add('https://www.searx.me/', callback=__test_callback)
    r.add('https://httpbin.org/delay/0', headers={'User-Agent': useragent}, callback=__test_callback)
    r.add('https://httpbin.org/delay/0', headers={'User-Agent': 'x'}, timeout=20000, callback=__test_callback)
    r.add('http://127.0.0.1:7777/', headers={'User-Agent': 'x'}, callback=__test_callback)
    r.add('https://httpbin.org/delay/0', cookies={'as': 'sa', 'bb': 'cc'}, callback=__test_callback)
    r.add('http://httpbin.org/delay/0', callback=__test_callback, timeout=10000, headers={'User-Agent': 'x'})
    r.add('https://www.google.com', callback=__test_callback)
    r.add('https://www.yahoo.com', callback=__test_callback)
    r.send_requests()
    '''
    print('---------------------')
    print(fetch('http://www.example.com', timeout=2000))
    '''
