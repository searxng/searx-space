import os
import sys
import asyncio
import tempfile
import subprocess
from urllib.parse import urljoin
from contextlib import asynccontextmanager

from lxml import etree

from searxstats.common.utils import exception_to_str, get_file_content_hash
from searxstats.common.http import new_client, get
from searxstats.common.html import extract_text, html_fromstring
from searxstats.config import set_database_url, get_database_url, DEBIAN_SOURCE_PACKAGE_NAMES, DEBIAN_GIT_URL
from searxstats.database import initialize_database, get_engine, new_session
from searxstats.data.update import insert_commit
from searxstats.data.query import is_commit_exists


# see "Depends" section of https://salsa.debian.org/debian/searx/-/blob/master/debian/control
# Be careful to take the source package name (twitter-bootstrap3, not libjs-bootstrap)
LINK_XPATH = etree.XPath("//td/a[@href]")


def get_package_index_url(package_name):
    return f'https://ftp.debian.org/debian/pool/main/{package_name[0]}/{package_name}/'


def get_deb_commit_id(package_name):
    return 'deb:' + package_name


async def get_deb_urls_for_package(session, package_url):
    """Parse one Apache index page
    * package_url is one of the URL in DEBIAN_SOURCE_PACKAGE_NAMES
    * return a list of deb URL.
    """
    print('  Downloading index', package_url)
    response, error = await get(session, package_url)
    if error is not None:
        print(package_url, error)
        raise Exception(error)
    document = await html_fromstring(response.text)
    result_element_list = LINK_XPATH(document)
    if len(result_element_list) == 0:
        return
    urls = {}
    for result_element in result_element_list:
        if extract_text(result_element) != 'Parent Directory':
            deb_name = result_element.get('href')
            deb_url = urljoin(package_url, deb_name)
            if deb_url.endswith('.deb'):
                urls[deb_name] = deb_url
    return urls


async def get_package_name_url_dict(session, source_package_name_list):
    """Return a dict, key are package name, values are URL.

    source_package_names is a list of source package names.
    """
    urls = {}
    for package_name in source_package_name_list:
        package_url = get_package_index_url(package_name)
        urls.update(await get_deb_urls_for_package(session, package_url))
    return urls


@asynccontextmanager
async def download_and_extract_deb(session, url):
    """Yield a temporary directory with the content of the deb downloaded from the url parameter
    """
    with tempfile.TemporaryDirectory() as tmpdirname:
        with tempfile.NamedTemporaryFile(suffix='.deb') as fdeb:
            response, error = await get(session, url)
            if error is not None:
                print(url, error)
                raise Exception(error)
            fdeb.write(response.content)
            cp = subprocess.run(['dpkg', '-x', fdeb.name, tmpdirname])
            if cp.returncode != 0:
                raise Exception('dpkg -x exit code = ' + str(cp.returncode))
            yield tmpdirname


def filename_iterator(deb_directory):
    """Iterator over filename of a deb content

    Ignore:
    * path usr/share/doc
    * extension .gz, .br
    * symbolic links
    """
    usr_share_doc_folder = os.path.join(deb_directory, 'usr/share/doc')
    for root, _, files in os.walk(deb_directory):
        if root.startswith(usr_share_doc_folder):
            continue
        for file in files:
            _, file_extension = os.path.splitext(file)
            if file_extension in ('.gz', '.br'):
                continue
            filename = os.path.join(root, file)
            if not os.path.islink(filename):
                yield filename


async def fetch_deb_hashes(session, url):
    """Return a list of content hashes of the .deb that can be downloaded from
    the url parameter.
    """
    print('  Processing', url)
    hashes = []
    async with download_and_extract_deb(session, url) as deb_directory:
        for filename in filename_iterator(deb_directory):
            try:
                hashes.append(get_file_content_hash(filename))
            except Exception as e:
                print('    Error', filename[len(deb_directory):], exception_to_str(e))
    return hashes


def filter_out_known_packages(name_url_dict):
    result = {}
    with get_engine().connect() as connection:
        with new_session(bind=connection) as session:
            for package_name, package_url in name_url_dict.items():
                if not is_commit_exists(session, get_deb_commit_id(package_name)):
                    result[package_name] = package_url
    return result


async def fetch_source_package_hashes(source_package_name_list):
    """For each source package, get all .deb, then for each .deb, get the hashes of files of the .deb.

    Return a dict, key are deb name, value is a list of hashes
    """
    async with new_client() as session:
        name_url_dict = await get_package_name_url_dict(session, source_package_name_list)
        name_url_dict = filter_out_known_packages(name_url_dict)
        hashes = {}
        for package_name, package_url in name_url_dict.items():
            hashes[package_name] = await fetch_deb_hashes(session, package_url)
        return hashes


async def fetch_hashes_from_deb_source_list(debian_git_url, debian_source_package_names):
    print(f'Update Debian package contents: {", ".join(debian_source_package_names)}')
    hashes = await fetch_source_package_hashes(debian_source_package_names)
    with get_engine().connect() as connection:
        for package_name, package_hashes in hashes.items():
            with new_session(bind=connection) as session:
                insert_commit(session, debian_git_url, get_deb_commit_id(package_name), package_hashes)
                session.commit()


def main():
    if len(sys.argv) == 2:
        database_url = sys.argv[1]
        set_database_url(database_url)

    database_url = get_database_url()
    print('database URL', database_url)
    initialize_database(database_url)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(fetch_hashes_from_deb_source_list(DEBIAN_GIT_URL, DEBIAN_SOURCE_PACKAGE_NAMES))


if __name__ == '__main__':
    main()
