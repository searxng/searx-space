import logging
import kronos
import random
import dateutil.parser
from lxml import html, etree
from datetime import timedelta

from .httpadapter import MultiRequest, fetch
from .models import Instance, Engine, Query, InstanceTest, Certificate, Url, URL_TYPE_HTTPS, URL_TYPE_TOR


@kronos.register('0 0 * * *')
def update():
    #
    instances = Instance.objects.order_by('install_since')

    # normal instances
    # deferred callbacks : make sure to never block reading of HTTP responses
    multi = MultiRequest(defer_callbacks=True, max_simultanous_connections=3)
    instance_test_ssl_pb = []
    for instance in instances:
        if instance.url != '':
            multi.add(instance.url,
                      timeout=20000,
                      callback=update_instance,
                      callback_parameters=(instance, instance_test_ssl_pb, URL_TYPE_HTTPS))
    multi.send_requests()

    # for normal instance with SSL problem, check again without SSL check
    multi = MultiRequest(defer_callbacks=True, max_simultanous_connections=3)
    for instance_test in instance_test_ssl_pb:
        multi.add(str(instance_test.url),
                  timeout=20000,
                  ssl_verification=False,
                  callback=update_instance_version,
                  callback_parameters=(instance_test, ))
    multi.send_requests()
    # TODO : check if Tor is working

    # Onion instances
    multi = MultiRequest(defer_callbacks=True, max_simultanous_connections=3)
    for instance in instances:
        if instance.hidden_service_url != '':
            multi.add(instance.hidden_service_url,
                      proxy='socks4://localhost:9050',
                      timeout=20000,
                      callback=update_instance,
                      callback_parameters=(instance, None, URL_TYPE_TOR))
    multi.send_requests()


# returns extract_text on the first result selected by the xpath or None
def extract_text_from_dom(dom, xpath):
    r = dom.xpath(xpath)
    if len(r) > 0:
        return r[0]
    return None


def get_searx_version(response_container):
    response_html = response_container.content.decode()
    try:
        dom = html.fromstring(response_html)
    except etree.XMLSyntaxError:
        # not a valid HTML document
        # TODO workaround with regex ?
        return ''

    searx_full_version = extract_text_from_dom(dom, "/html/head/meta[@name='generator']/@content")
    if searx_full_version is None:
        searx_version = ''
    else:
        s = searx_full_version.split('/')
        if len(s) == 2:
            searx_version = s[1]
        else:
            searx_version = searx_full_version
    return searx_version


def update_instance(response_container, instance, instance_test_ssl_pb, url_type):
    logging.info('update instance {0}'.format(response_container.url))

    # get response time
    pretransfer_response_time = timedelta(seconds=response_container.timings['TOTAL_TIME'])
    total_response_time = timedelta(seconds=response_container.timings['TOTAL_TIME'])
    url = get_url(response_container.url)

    # get certificate
    certificate = None
    if len(response_container.certinfo) > 0:
        curl_certificate = response_container.certinfo[0]
        certificate = get_certificate(curl_certificate)

    if response_container.curl_error_code is None:
        # connection ok
        http_status_code = response_container.status_code
        curl_error_message = ''
        # read searx version
        searx_version = get_searx_version(response_container)
        valid_instance = (searx_version != '')
    else:
        # connection error
        http_status_code = None
        curl_error_message = response_container.curl_error_message
        searx_version = ''
        valid_instance = False

    it = InstanceTest(instance=instance,
                      url=url,
                      url_type=url_type,
                      pretransfer_response_time=pretransfer_response_time,
                      total_response_time=total_response_time,
                      certificate=certificate,
                      connection_error_message=curl_error_message,
                      valid_ssl=valid_instance,   # bug ?
                      http_status_code=http_status_code,
                      valid_instance=valid_instance,
                      searx_version=searx_version,)
    update_aggregate_id(it)
    it.save()

    # if SSL error, check again without SSL verification after
    # see https://curl.haxx.se/libcurl/c/libcurl-errors.html
    # 35: A problem occurred somewhere in the SSL/TLS handshake.
    # 51: The remote server's SSL certificate or SSH md5 fingerprint was deemed not OK.
    # 58: problem with the local client certificate.
    # 59: Couldn't use specified cipher.
    # 60: Peer certificate cannot be authenticated with known CA certificates.
    # 83: Issuer check failed
    # 90: Failed to match the pinned key specified with CURLOPT_PINNEDPUBLICKEY.
    # 91: Status returned failure when asked with CURLOPT_SSL_VERIFYSTATUS.
    if instance_test_ssl_pb is not None and response_container.curl_error_code in [35, 51, 58, 59, 60, 83, 90, 91]:
        instance_test_ssl_pb.append(it)


def update_instance_version(response_container, instancetest):
    if response_container.curl_error_code is None:
        instancetest = InstanceTest.objects.get(pk=instancetest.pk)
        instancetest.valid_ssl = False
        instancetest.searx_version = get_searx_version(response_container)
        instancetest.valid_instance = (instancetest.searx_version != '')
        certificate = None
        if len(response_container.certinfo) > 0:
            curl_certificate = response_container.certinfo[0]
            instancetest.certificate = get_certificate(curl_certificate)
        update_aggregate_id(instancetest)
        instancetest.save()


def update_aggregate_id(instancetest):
    # get the last aggregate_id
    lastrecord = InstanceTest.objects.filter(instance=instancetest.instance)\
                 .order_by('-timestamp')\
                 .first()
    if lastrecord is None:
        aggregate_id = 0
    else:
        aggregate_id = lastrecord.aggregate_id

    # get the last test for the same URL
    if (lastrecord is None) or (lastrecord.url != instancetest.url):
        lastrecord = InstanceTest.objects.filter(instance=instancetest.instance, url=instancetest.url)\
                                         .order_by('-timestamp')\
                                         .first()

    # if the two test can aggregate keeps the same id
    # can_aggregate accepts None
    if instancetest.can_aggregate(lastrecord):
        instancetest.aggregate_id = aggregate_id
    else:
        # is it the first test for this aggregate_id and URL
        lastrecord = InstanceTest.objects.filter(instance=instancetest.instance, aggregate_id=aggregate_id, url=instancetest.url)\
                                         .order_by('-timestamp')\
                                         .first()
        if lastrecord is not None:
            instancetest.aggregate_id = aggregate_id + 1
        else:
            instancetest.aggregate_id = aggregate_id


def get_url(url_string):
    if url_string is None:
        return None

    # get_or_create(defaults=None, **kwargs) ?
    urls = Url.objects.filter(url=url_string)

    if len(urls) > 0:
        return urls[0]

    url = Url(url=url_string)
    url.save()
    return url


def get_certificate(curl_certificate):
    # safety net : None
    if curl_certificate is None:
        return None

    #
    start_date = dateutil.parser.parse(curl_certificate['Start date'])
    expire_date = dateutil.parser.parse(curl_certificate['Expire date'])

    # lookup
    certificates = Certificate.objects.filter(
        signature=curl_certificate['Signature'],
        signature_algorithm=curl_certificate['Signature Algorithm'],
        start_date=start_date,
        expire_date=expire_date,
        issuer=curl_certificate['Issuer'],
        subject=curl_certificate['Subject'],
        cert=curl_certificate['Cert'],
    )

    if len(certificates) > 0:
        # found
        return certificates[0]

    # not found : create a new one
    certificate = Certificate(
        signature=curl_certificate['Signature'],
        signature_algorithm=curl_certificate['Signature Algorithm'],
        start_date=start_date,
        expire_date=expire_date,
        issuer=curl_certificate['Issuer'],
        subject=curl_certificate['Subject'],
        cert=curl_certificate['Cert'],
    )
    certificate.save()
    return certificate
