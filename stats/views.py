from django.shortcuts import render, get_object_or_404

# Create your views here.
from django.http import HttpResponse
from django.template import loader
from django.db.models import Count, Max, Min, Avg, Q
from django.views.generic.list import ListView
from django.views.decorators.cache import cache_page

from .models import Instance, Engine, Certificate, Query, InstanceTest, Url, UrlCache, ObjectCache

HTTP_CODE = {
    # 2xx
    200: 'OK',

    # 3xx
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',

    # 4xx
    400: 'Bad Request',
    401: 'Unauthorized',
    403: 'Forbidden',
    404: 'Not Found',
    408: 'Request Timeout',

    # NGINX
    444: 'No Response',
    495: 'SSL Certificate Error',
    496: 'SSL Certificate Required',
    497: 'HTTP Request Sent to HTTPS Port',
    499: 'Client Closed Request',

    # Standard
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    511: 'Network Authentication Required',

    # CloudFlare
    520: 'CloudFlare: Unknown Error',
    521: 'CloudFlare: Web Server Is Down',
    522: 'Connection Timed Out',
    523: 'Origin Is Unreachable',
    524: 'A Timeout Occurred',
    525: 'SSL Handshake Failed',
    526: 'Invalid SSL Certificate',
}


class DictObjWrapper(object):

    def __init__(self, d):
        self.__dict__ = d


def add_viewinfo(instancetest):
    if instancetest.connection_error_message != '':
        # connection problem
        instancetest.result_class = 'label-danger'
        instancetest.result_msg = instancetest.connection_error_message
    elif not instancetest.valid_instance and instancetest.http_status_code < 300:
        # connection is working and get HTTP response but there is no searx instance
        instancetest.result_class = 'label-danger'
        instancetest.result_msg = str(instancetest.http_status_code) + ' - Not a valid Searx instance'
    else:
        # connection ok, display HTTP error code
        instancetest.result_msg = str(instancetest.http_status_code) \
                                  + ' - ' + HTTP_CODE.get(instancetest.http_status_code, '')
        if instancetest.http_status_code < 300:
            # valid instance because it was tested before
            instancetest.result_class = 'label-success'
        elif instancetest.http_status_code < 400:
            instancetest.result_class = 'label-warning'
        else:
            instancetest.result_class = 'label-danger'


def get_last_instancetest(instance, url_pk):
    instancetest = None

    if url_pk is not None:
        # find the last test
        instancetest = instance.instancetest_set.select_related('certificate').filter(url=url_pk).latest('timestamp')
        if instancetest is not None:
            # there is one
            add_viewinfo(instancetest)
        else:
            # there is no test
            instancetest = {}
            instancetest['result_class'] = 'label-default'
            instancetest['result_msg'] = 'Untested'
            instancetest['url'] = url
            instancetest['instance_pk'] = instance.pk

    return instancetest


# @cache_page(60 * 15)
def index(request):
    # cache
    urlcache = UrlCache()

    # for all instances
    instancetest_list = []
    odd = True
    for instance in Instance.objects.all():
        count = 0
        instancetest_normal = get_last_instancetest(instance, urlcache.url_to_pk(instance.url))
        if instancetest_normal is not None:
            # to avoid a request
            instancetest_normal.url = urlcache.url_to_obj(instance.url)
            # template
            instancetest_normal.odd = odd
            instancetest_normal.first = True
            count = count + 1
            instancetest_list.append(instancetest_normal)

        instancetest_hidden = get_last_instancetest(instance, urlcache.url_to_pk(instance.hidden_service_url))
        if instancetest_hidden is not None:
            # to avoid a request
            instancetest_hidden.url = urlcache.url_to_obj(instance.hidden_service_url)
            # template
            instancetest_hidden.odd = odd
            if count > 0:
                instancetest_hidden.linked = True
            else:
                instancetest_hidden.first = True
            count = count + 1
            instancetest_list.append(instancetest_hidden)

        if count > 0:
            odd = not odd

    # rendering
    template = loader.get_template('stats/index.html')
    context = {
        'instancetest_list': instancetest_list,
    }
    return HttpResponse(template.render(context, request))


def instance(request, instance_id):
    instance = get_object_or_404(Instance, pk=instance_id)

    urlcache = UrlCache()
    url = urlcache.url_to_obj(instance.url)
    if url is None:
        url = urlcache.url_to_obj(instance.hidden_service_url)

    certificatecache = ObjectCache(Certificate)

    instancetest_list = InstanceTest.objects.filter(instance=instance.pk)\
        .values('aggregate_id', 'url_type', 'url',
                'certificate', 'connection_error_message', 'valid_ssl',
                'http_status_code', 'valid_instance', 'searx_version')\
        .annotate(Min('timestamp'), Max('timestamp'), Avg('total_response_time'))\
        .order_by('-aggregate_id', 'url_type')

    it_list = []
    previous_aggregate_id = -1
    current_timestamp = None
    for instancetest in instancetest_list:
        it = DictObjWrapper(instancetest)
        it.url = urlcache.pk_to_obj(it.url)
        if it.certificate is not None:
            it.certificate = certificatecache.get(it.certificate)
        it.total_response_time__avg = it.total_response_time__avg / 1000000
        add_viewinfo(it)
        it.odd = (it.aggregate_id % 2 == 0)
        if previous_aggregate_id != it.aggregate_id:
            previous_aggregate_id = it.aggregate_id
            it.first = True
            current_timestamp = it.timestamp__min
        else:
            it.linked = True
            print(it.timestamp__min - current_timestamp, current_timestamp, it.timestamp__min)
        it_list.append(it)

    instancetest_list = it_list

    template = loader.get_template('stats/instance.html')
    context = {
        'instance': instance,
        'instancetest_list': instancetest_list,
    }
    return HttpResponse(template.render(context, request))


def engine_list(request):
    return HttpResponse('')


def engine(request, instance):
    return HttpResponse('')
