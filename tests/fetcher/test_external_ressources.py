# pylint: disable=unused-argument, redefined-outer-name

import hashlib
import base64

import pytest
import pytest_httpserver

import searxstats.common.memoize
import searxstats.model
import searxstats.fetcher.external_ressources as external_ressources


DATA_INDEX = """<!DOCTYPE html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Test external_ressources</title>
  <script type="text/javascript" src="index.js"></script>
  <link rel="stylesheet" href="index.css" type="text/css" />
  <script>{0}</script>
</head>
<body>
<main>
<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer tempus faucibus enim sodales tempus.</p>
<p>Mauris aliquet dolor non ante bibendum, vel porta risus scelerisque. Integer eget tristique erat.</p>
<p>Curabitur ultrices vitae risus eget auctor. Donec a sollicitudin enim.</p>
<p>Suspendisse tempor, libero aliquam gravida suscipit, nisi nisi viverra erat,
a euismod nunc libero sit amet leo. Nunc euismod augue erat, ut eleifend nisl lobortis id. </p>
</main>
<script>{0}</script>
</body>
</html>
"""

DATA_INLINE_JS = "dummy= 'test'"

DATA_INDEX_JS = """
console.log('ok');
"""

DATA_INDEX_CSS = """
main:first-child {
    width: auto;
}
"""

FAVICON_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAA0AAAAlCAYAAACZFGMnAAAAIklEQVR42mMUWPv2PwOJgHFU06imUU2jmkY1jW" +\
                 "oa1UQXTQCsFGKTXwPYFgAAAABJRU5ErkJggg=="
FAVICON_BINARY = base64.b64decode(FAVICON_BASE64)


def get_sha256_binary(binary):
    sha256_hash = hashlib.sha256()
    sha256_hash.update(binary)
    return sha256_hash.hexdigest()


def get_sha256(content):
    return get_sha256_binary(content.encode('utf-8'))


def find_sha256_info(ressource_hashes, content) -> dict:
    lookfor = get_sha256(content)
    for sha256, info in ressource_hashes.items():
        if sha256 == lookfor:
            return info
    return None


@pytest.fixture
def fake_httpserver(httpserver):
    httpserver.expect_request('/index.html').\
        respond_with_data(DATA_INDEX.format(DATA_INLINE_JS),
                          content_type='text/html')
    httpserver.expect_request('/index.js').\
        respond_with_data(
            DATA_INDEX_JS, content_type='application/javascript; charset=utf-8')
    httpserver.expect_request('/index.css').\
        respond_with_data(DATA_INDEX_CSS, content_type='text/css')
    httpserver.expect_request('/favicon.ico').\
        respond_with_data(FAVICON_BINARY, content_type='image/png')
    yield httpserver


@pytest.fixture
def fake_searxstatisticsresult(fake_httpserver):
    result = searxstats.model.SearxStatisticsResult()
    result.update_instance(fake_httpserver.url_for('index.html'), {
        'http': {
            'status_code': 200,
            'error': None
        },
        'version': '0.15.0',
        'timing': {
            'initial': 200
        }
    })
    yield result


@pytest.fixture
def selenium_driver():
    driver = external_ressources.new_driver()
    try:
        yield driver
    finally:
        driver.close()


def test_fetch_ressource_hashes_js(selenium_driver, fake_httpserver: pytest_httpserver.HTTPServer):
    ressources = external_ressources.fetch_ressource_hashes_js.no_memoize(
        selenium_driver, fake_httpserver.url_for('/index.html'))

    assert isinstance(ressources, dict)
    for hashes_key in ['inline_script', 'inline_style', 'link', 'script']:
        assert hashes_key in ressources
    assert ressources['inline_script'][0]['hash'] == get_sha256(DATA_INLINE_JS)
    assert list(ressources['link'].values())[0]['hash'] == get_sha256(DATA_INDEX_CSS)
    assert list(ressources['script'].values())[0]['hash'] == get_sha256(DATA_INDEX_JS)
    if 'other' in ressources:
        # Firefox may not load the favicon, no deterministic behavior
        assert list(ressources['other'].values())[0]['hash'] == get_sha256_binary(FAVICON_BINARY)

    ressource_hashes = {
        'index': 0,
    }
    external_ressources.replace_hash_by_hashref(ressources, ressource_hashes)

    data_inline_js_info = find_sha256_info(ressource_hashes, DATA_INLINE_JS)
    data_index_css_info = find_sha256_info(ressource_hashes, DATA_INDEX_CSS)
    data_index_js_info = find_sha256_info(ressource_hashes, DATA_INDEX_JS)

    assert isinstance(data_inline_js_info, dict)
    assert isinstance(data_index_js_info, dict)
    assert isinstance(data_index_css_info, dict)

    # twice the same inline script, but still count as one for the instance
    assert data_inline_js_info['count'] == 1
    assert data_index_css_info['count'] == 1
    assert data_index_js_info['count'] == 1

    assert ressources['inline_script'][0]['hashRef'] == data_inline_js_info['index']
    assert list(ressources['script'].values())[0]['hashRef'] == data_index_js_info['index']
    assert list(ressources['link'].values())[0]['hashRef'] == data_index_css_info['index']


def test_fetch(selenium_driver,
               fake_httpserver: pytest_httpserver.HTTPServer,
               fake_searxstatisticsresult):
    searxstats.common.memoize.nobinding()
    external_ressources.fetch(fake_searxstatisticsresult)
