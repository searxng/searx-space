import logging
import kronos
import random
import dateutil.parser
from lxml import html, etree
from datetime import timedelta

from .httpadapter import MultiRequest
from .models import Instance, Engine, Query, InstanceTest, Certificate, Url


@kronos.register('0 0 * * *')
def update():
    instances = Instance.objects.order_by('install_since')
    
    # normal instances
    '''
    deferred callbacks : make sure to never block reading of HTTP responses
    '''
    multi = MultiRequest(defer_callbacks=True)
    instance_test_ssl_pb = []
    for instance in instances:
        if instance.url != '':
            multi.add(instance.url,
                      timeout=20,
                      callback=update_instance,
                      callback_parameters=(instance, instance_test_ssl_pb))
    multi.send_requests()

    # for normal instance with SSL problem, check again without SSL check
    multi = MultiRequest(defer_callbacks=True)
    for instance_test in instance_test_ssl_pb:
        multi.add(str(instance_test.url),
                  timeout=20,
                  ssl_verification=False,
                  callback=update_instance_version,
                  callback_parameters=(instance_test, ))
    multi.send_requests()

    # Onion instances
    '''
    multi = MultiRequest(defer_callbacks=True)
    for instance in instances:
        if instance.hidden_service_url != '':
            multi.add(instance.hidden_service_url,
                      proxy='socks4a://localhost:9050',
                      timeout=20,
                      callback=update_instance,
                      callback_parameters=(instance, ))
    multi.send_requests()
    '''


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
        # TODO workaround with regex
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


def update_instance(response_container, error_code, error_message, instance, instance_test_ssl_pb):
    logging.info('update instance {0}'.format(response_container.url))

    response_time = timedelta(seconds=response_container.timings['TOTAL_TIME'])
    url = get_url(response_container.url)

    certificate = None
    if len(response_container.certinfo) > 0:
        curl_certificate = response_container.certinfo[0]
        certificate = get_certificate(curl_certificate)

    if error_code is None:
        http_result = response_container.status_code
        searx_version = get_searx_version(response_container)
        valid_instance = (searx_version != '')
        error_message = ''
    else:
        valid_instance = False
        http_result = 0
        searx_version = ''
    
    it = InstanceTest(instance=instance, 
                      url=url,
                      response_time=response_time, 
                      searx_version=searx_version, 
                      http_result=http_result,
                      error_message = error_message,
                      certificate = certificate,
                      valid_ssl = valid_instance,
                      valid_instance = valid_instance
                     )
    it.save()

    # if SSL error, check again without SSL verification after
    if error_code in [35, 51, 58, 59, 60, 83, 90, 91]:
        instance_test_ssl_pb.append(it)


def update_instance_version(response_container, error_code, error_message, instance_test):
    if error_code is None:
        instance_test = InstanceTest.objects.get(pk=instance_test.pk)
        instance_test.searx_version = get_searx_version(response_container)
        instance_test.valid_ssl = False
        instance_test.valid_instance = (instance_test.searx_version != '')
        instance_test.save()


def get_url(url_string):
    if url_string is None:
        return None

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
        signature = curl_certificate['Signature'],
        signature_algorithm = curl_certificate['Signature Algorithm'],
        start_date = start_date,
        expire_date = expire_date,
        issuer = curl_certificate['Issuer'],
        subject = curl_certificate['Subject'],
        cert = curl_certificate['Cert'],
    )

    if len(certificates) > 0:
        # found
        return certificates[0]

    # not found : create a new one
    certificate = Certificate(
        signature = curl_certificate['Signature'],
        signature_algorithm = curl_certificate['Signature Algorithm'],
        start_date = start_date,
        expire_date = expire_date,
        issuer = curl_certificate['Issuer'],
        subject = curl_certificate['Subject'],
        cert = curl_certificate['Cert'],
    )
    certificate.save()
    return certificate
