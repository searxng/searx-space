from datetime import timedelta
import kronos
import random
from lxml import html, etree

from .httpadapter import MultiRequest
from .models import Instance, Engine, Query, InstanceTest


@kronos.register('0 0 * * *')
def update():
    instances = Instance.objects.order_by('install_since')
    
    # normal instances
    multi = MultiRequest()
    for instance in instances:
        if instance.url != '':
            multi.add(instance.url, callback=update_instance, callback_parameters=(instance, ))
    multi.send_requests()

    # Onion instances
    # TODO


# returns extract_text on the first result selected by the xpath or None
def extract_text_from_dom(dom, xpath):
    r = dom.xpath(xpath)
    if len(r) > 0:
        return r[0]
    return None


def update_instance(response_container, error, instance):
    if error is None:
        http_result = response_container.status_code
        response_time = timedelta(seconds=response_container.timings[0][1])
        
        response_html = response_container.content.decode()
        dom = html.fromstring(response_html)
        searx_full_version = extract_text_from_dom(dom, "/html/head/meta[@name='generator']/@content")
        if searx_full_version is None:
            searx_version = ''
        else:
            s = searx_full_version.split('/')
            if len(s) == 2:
                searx_version = s[1]
            else:
                searx_version = searx_full_version

        error_message = ''
    else:
        http_result = 0
        response_time = timedelta(seconds=response_container.timings[0][1])
        searx_version = ''
        error_message = error[1]
    
    it = InstanceTest(instance=instance, 
                      response_time=response_time, 
                      searx_version=searx_version, 
                      http_result=http_result,
                      error_message = error_message)
    it.save()


