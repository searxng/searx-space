import logging
import pycurl
import certifi
import threading
from itertools import cycle
from io import BytesIO
from time import time
from concurrent.futures import ThreadPoolExecutor


def no_callback(*args):
    pass


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
                 timeout=5.0,
                 ssl_verification=True,
                 proxy=None
                 ):

        if headers is None:
            headers = {}

        if cookies is None:
            cookies = {}

        if callback is None:
            callback = no_callback

        if callback_parameters is None:
            callback_parameters = ()

        if data is not None:
            curl_handler.setopt(curl_handler.POSTFIELDS, urlencode(data))

        if proxy is not None:
            curl_handler.setopt(curl_handler.PROXY, proxy)

        self.url = url
        self.headers = headers
        self.cookies = cookies
        self.timeout = int(timeout * 1000)  # in milisecs
        self.callback = callback
        self.callback_parameters = callback_parameters
        self.curl_handler = curl_handler

        self._response_buffer = BytesIO()
        self.response = None
        curl_handler.setopt(curl_handler.WRITEFUNCTION, self._response_buffer.write)
        curl_handler.setopt(curl_handler.SSL_VERIFYPEER, int(ssl_verification))

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
        certinfo = self.curl_handler.getinfo(pycurl.INFO_CERTINFO)
        dictcertinfo = []
        for cert in certinfo:
            d = {}
            for k, v in cert:
                d[k] = v
            dictcertinfo.append(d)

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


class MultiRequest(object):
    def __init__(self, multi_handler=None, defer_callbacks=False):
        self.requests = {}

        self._defer_callbacks = defer_callbacks

        if multi_handler:
            self._curl_multi_handler = multi_handler
        else:
            self._curl_multi_handler = pycurl.CurlMulti()

    def add(self, url, **kwargs):
        handle = get_connection()
        request_container = RequestContainer(url, handle, **kwargs)
        try:
            self._curl_multi_handler.add_handle(handle)
            self.requests[handle] = request_container
        except pycurl.error as error:
            print(error)

    def _init(self):
        self._async_callbacks = []
        self._async_results = []

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
        self._init()

        if len(self.requests) == 0:
            return False

        select_timeout = 0.5

        # set timeout
        timeout = max(c.timeout for c in self.requests.values())
        for h, c in self.requests.items():
            h.setopt(h.CONNECTTIMEOUT_MS, timeout)
            h.setopt(h.TIMEOUT_MS, timeout)
            h.setopt(h.URL, c.url)
            c.headers['Connection'] = 'keep-alive'

            h.setopt(h.HTTPHEADER,
                     ['{0}: {1}'.format(k, v)
                      for k, v in c.headers.items()])

            if c.cookies:
                h.setopt(h.COOKIE, '; '.join('{0}={1}'.format(k, v)
                                             for k, v in c.cookies.items()))
            else:
                h.unsetopt(h.COOKIE)

        send_start = time()
        handles_num = len(self.requests)
        results = []
        while handles_num:
            ret = self._curl_multi_handler.select(select_timeout)
            if ret == -1:
                continue
            while 1:
                ret, new_handles_num = self._curl_multi_handler.perform()
                # handle finished
                if new_handles_num < handles_num:
                    _, success_list, error_list = self._curl_multi_handler.info_read()
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
                future.result(timeout=remaining_time)
            except TimeoutError:
                logging.warning('engine timeout: {0}'.format(th._engine_name))

        return True


'''

'''


def fetch(url, **kwargs):
    response_container = None

    def c(_response_container):
        response_container = _response_container

    multi = MultiRequest()
    multi.add(url, callback=c, **kwargs)
    multi.send_requests()
    return response_container


# Thread pool with the GIL limitation
POOL = ThreadPoolExecutor(8)

if __name__ == '__main__':
    def __test_callback0(responseContainer):
        pass

    def __test_callback(responseContainer, www):
        print(www)
        if responseContainer is not None:
            print(responseContainer.url)
            print(responseContainer.curl_error_code)
            print(responseContainer.curl_error_message)
            print(responseContainer.status_code)
            print(responseContainer.content_type)
            if len(responseContainer.certinfo) > 0:
                print(responseContainer.certinfo[0]['Signature'])
                print(responseContainer.certinfo[0]['Expire date'])
                print(responseContainer.certinfo[0])
            for k, v in responseContainer.timings.items():
                print("{name} {time}".format(name=k, time=v))

    r = MultiRequest(defer_callbacks=False)
    useragent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36'
    r.add('https://www.searx.me/', headers={'User-Agentxx': useragent}, callback=__test_callback, callback_parameters=('aaaa',))
    # r.add('https://httpbin.org/delay/0', headers={'User-Agent': 'x'}, callback=__test_callback, callback_parameters=('aaaa',))
    # r.add('https://httpbin.org/delay/0', headers={'User-Agent': 'x'}, timeout=20, callback=__test_callback0)
    # r.add('http://127.0.0.1:7777/', headers={'User-Agent': 'x'})
    # r.add('https://httpbin.org/delay/0', cookies={'as': 'sa', 'bb': 'cc'})
    # r.add('http://httpbin.org/delay/0', callback=__test_callback, timeout=1.0, headers={'User-Agent': 'x'})
    r.send_requests()

    print('---------------------')
    print(fetch('http://www.example.com'))
