import logging
import pycurl
import certifi
import threading
from itertools import cycle
from io import BytesIO
from time import time
from concurrent.futures import ThreadPoolExecutor

MULTI_HANDLER = pycurl.CurlMulti()


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

    def extract_response(self):
        infos = (
            ("TOTAL_TIME", pycurl.TOTAL_TIME),
            ("NAMELOOKUP_TIME", pycurl.NAMELOOKUP_TIME),
            ("CONNECT_TIME", pycurl.CONNECT_TIME),
            ("PRETRANSFER_TIME" ,pycurl.PRETRANSFER_TIME),
            ("STARTTRANSFER_TIME", pycurl.STARTTRANSFER_TIME),
            ("REDIRECT_TIME", pycurl.REDIRECT_TIME),
            ("REDIRECT_COUNT", pycurl.REDIRECT_COUNT)
        )

        timings = []

        for i in infos:
            timings.append((i[0], self.curl_handler.getinfo(i[1])))

        body = self._response_buffer.getvalue()
        status_code = self.curl_handler.getinfo(pycurl.HTTP_CODE)
        content_type = self.curl_handler.getinfo(pycurl.CONTENT_TYPE)
        # print(self.curl_handler.getinfo(pycurl.CERTINFO))
        self.response = ResponseContainer(self.url, body, status_code, content_type, timings)


class ResponseContainer(object):
    def __init__(self, url, body, status_code, content_type, timings):
        self.text = self.content = body
        self.status_code = status_code
        self.url = url
        self.content_type = content_type
        self.timings = timings        


class MultiRequest(object):
    def __init__(self, multi_handler=None):
        self.requests = {}

        if multi_handler:
            self._curl_multi_handler = multi_handler
        else:
            self._curl_multi_handler = MULTI_HANDLER

    def add(self, url, **kwargs):
        handle = get_connection()
        request_container = RequestContainer(url, handle, **kwargs)
        try:
            self._curl_multi_handler.add_handle(handle)
        except:
            print('meep')
            pass
        self.requests[handle] = request_container

    def send_requests(self):
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

        search_start = time()
        handles_num = len(self.requests)
        async_results = []
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
                        # calling callbacks
                        async_results.append(POOL.submit(self.requests[h].callback, 
                                                         self.requests[h].response,
                                                         None,
                                                         *self.requests[h].callback_parameters))
                    for h, err_code, err_string in error_list:
                        logging.warn('Error on %s: "%s"', self.requests[h].url, err_string)
                        self.requests[h].extract_response()
                        async_results.append(POOL.submit(self.requests[h].callback, 
                                                         self.requests[h].response,
                                                         (err_code, err_string),
                                                         *self.requests[h].callback_parameters))

                    handles_num -= len(success_list) + len(error_list)
                if ret != pycurl.E_CALL_MULTI_PERFORM:
                    break

        for future in async_results:
            remaining_time = max(0.0, timeout - (time() - search_start))
            try:
                future.result(timeout = remaining_time)
            except TimeoutError:
                logging.warning('engine timeout: {0}'.format(th._engine_name))

        self._curl_multi_handler.close()
        return self.requests.values()


# Thread pool with the GIL limitation
POOL = ThreadPoolExecutor(8)

if __name__ == '__main__':
    def __test_callback0(responseContainer):
        pass

    def __test_callback(responseContainer, error, aaaa):
        if responseContainer is not None:
            print(responseContainer.url)
            print(responseContainer.status_code)
            print(responseContainer.content_type)
            for i in responseContainer.timings:
                print("{name} {time}".format(name=i[0], time=i[1]))
        else:
            print(error[0])
            print(error[1])
        print(aaaa)


    r = MultiRequest()
    r.add('https://www.searx.de/', headers={'User-Agent': 'x'}, callback=__test_callback, callback_parameters=('aaaa',))
    # r.add('https://httpbin.org/delay/0', headers={'User-Agent': 'x'}, callback=__test_callback, callback_parameters=('aaaa',))
    # r.add('https://httpbin.org/delay/0', headers={'User-Agent': 'x'}, timeout=20, callback=__test_callback0)
    # r.add('http://127.0.0.1:7777/', headers={'User-Agent': 'x'})
    # r.add('https://httpbin.org/delay/0', cookies={'as': 'sa', 'bb': 'cc'})
    # r.add('http://httpbin.org/delay/0', callback=__test_callback, timeout=1.0, headers={'User-Agent': 'x'})
    for v in r.send_requests():
        print(v.url)
        # print(v.status_code)
        # print(v.response.text)
