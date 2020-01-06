# pylint: disable=unused-argument, redefined-outer-name
import pytest
import pytest_httpserver

import searxstats.common.http as http


def test_get_host():
    assert http.get_host('https://en.wikipedia.org/wiki/Searx') == 'en.wikipedia.org'
    assert http.get_host('https://www.wikidata.org/wiki/Wikidata:Main_Page') == 'www.wikidata.org'
    assert http.get_host('https://en.wikipedia.org/wiki/Metasearch_engine') == 'en.wikipedia.org'


@pytest.mark.asyncio
async def test_new_client():
    async with http.new_client() as session:
        cookies = session.cookies
    assert cookies is not None


@pytest.mark.asyncio
async def test_do_get_ok(httpserver: pytest_httpserver.HTTPServer):
    httpserver.expect_request('/index.html').\
        respond_with_data('OK', content_type='text/html')

    async with http.new_client() as session:
        response, error = await http.get(session, httpserver.url_for('/index.html'))

    assert response.text == 'OK'
    assert error is None


@pytest.mark.asyncio
async def test_do_get_404(httpserver: pytest_httpserver.HTTPServer):
    httpserver.expect_request('/404.html').\
        respond_with_data('Not Found', content_type='text/html', status=404)

    async with http.new_client() as session:
        response, error = await http.get(session, httpserver.url_for('/404.html'))

    assert response.text == 'Not Found'
    assert error == 'HTTP status code 404'


@pytest.mark.asyncio
async def test_do_get_connection_refused(httpserver: pytest_httpserver.HTTPServer):
    httpserver.expect_request('/index.html').\
        respond_with_data('Not Found', content_type='text/html', status=404)
    # close HTTP server on purpose: make sure the connection will be refused
    httpserver.stop()
    try:
        async with http.new_client() as session:
            response, error = await http.get(session, httpserver.url_for('/index.html'))
    finally:
        # start again to avoid side effect
        httpserver.start()

    assert response is None
    assert error == 'Connection refused'
