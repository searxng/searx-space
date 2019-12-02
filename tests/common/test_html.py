# pylint: disable=unused-argument, redefined-outer-name
from lxml import etree

import pytest

import searxstats.common.html as html


@pytest.mark.asyncio
async def test_html_fromstring():
    results_xpath = etree.XPath("//a[contains(@class,'result-default')]")
    doc = await html.html_fromstring('<div><a href="http://localhost" class="result-default result">text</a></div>')

    links = []
    for element in results_xpath(doc):
        links.append(html.extract_text(element))

    assert len(links) == 1
    assert links[0] == 'text'


@pytest.mark.asyncio
async def test_html_fromstring_long():
    results_xpath = etree.XPath("//div[@id='main_results']/div[contains(@class,'result-default')]/h4/a")
    text = """
<!DOCTYPE html>
<html class="no-js" lang="en" >
<head>
<title>Sample</title>
</head>
<body>
<div class="row">
  <div class="col-sm-8" id="main_results">
    <h1 class="sr-only">Résultats de recherche</h1>
    <div class="result result-default">
      <h4 class="result_header"><a href="https://www.searx.me/" target="_blank" rel="noopener noreferrer"><span class="highlight">Searx</span></a></h4>
      <p class="result-content"><span class="highlight">searx</span> - a privacy-respecting, hackable metasearch engine. Start search. Advanced settings</p>
      <div class="clearfix"></div>
      <div class="pull-right">
        <span class="label label-default">yandex</span>
        <span class="label label-default">duckduckgo</span>
        <small><a href="https://web.archive.org/web/https://www.searx.me/" class="text-info" target="_blank" rel="noopener noreferrer"><span class="glyphicon glyphicon-link"></span>en cache</a></small>
        <small><a href="https://a.searx.space/morty/?mortyurl=https%3A%2F%2Fwww.searx.me%2F&amp;mortyhash=f135947bb007d79fcba4f00c290520275bf1f6e6d980a64a294f3f1b139fb571" class="text-info" target="_blank" rel="noopener noreferrer"><span class="glyphicon glyphicon-sort"></span>proxifié</a></small>
      </div>
      <div class="external-link">https://www.searx.me/</div>
    </div>
    <div class="result result-default">
      <h4 class="result_header"><a href="https://en.wikipedia.org/wiki/Searx" target="_blank" rel="noopener noreferrer"><span class="highlight">Searx</span> - Wikipedia</a></h4>
      <p class="result-content"><span class="highlight">searx</span> (/ s ɜːr k s /) is a free metasearch engine, available under the GNU Affero General Public License version 3, with the aim of protecting the privacy of its users. To this end, <span class="highlight">searx</span> does not share users' IP addresses or search history with the search engines from which it gathers results. Tracking cookies served by the search engines are blocked, preventing user-profiling-based results ...</p>
      <div class="clearfix"></div>
      <div class="pull-right">
        <span class="label label-default">yandex</span>
        <span class="label label-default">duckduckgo</span>
        <small><a href="https://web.archive.org/web/https://en.wikipedia.org/wiki/Searx" class="text-info" target="_blank" rel="noopener noreferrer"><span class="glyphicon glyphicon-link"></span>en cache</a></small>
        <small><a href="https://a.searx.space/morty/?mortyurl=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FSearx&amp;mortyhash=a0e621b0dd253f0b2c67dccee789cc43de95b7ca348a2dcf6eecbfeaa91651e4" class="text-info" target="_blank" rel="noopener noreferrer"><span class="glyphicon glyphicon-sort"></span>proxifié</a></small>
      </div>
      <div class="external-link">https://en.wikipedia.org/wiki/Searx</div>
    </div>
  </div>
</body>
</html>
    """  # noqa
    doc = await html.html_fromstring(text)

    links = []
    for element in results_xpath(doc):
        links.append(html.extract_text(element))

    assert len(links) == 2
    assert links[0] == 'Searx'
    assert links[1] == 'Searx - Wikipedia'
