from django.shortcuts import render, get_object_or_404

# Create your views here.
from django.http import HttpResponse
from django.template import loader
from django.db.models import Count, Max

from .models import Instance, Engine, Query, InstanceTest

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


'''
  TO OPTIMIZE
  AND NOT REALIBLE (assume the last test for an instance has the highest id)
'''


def index(request):
    # get all instances
    instances = Instance.objects.annotate(last_test_id=Max('instancetest')).exclude(url='').order_by('install_since')
    # get all last tests for all instances
    instance_test_ids = []
    instance_tests = {}
    for instance in instances:
        instance_test_ids.append(instance.last_test_id)
    # fetch the tests from the database
    instance_test_list = InstanceTest.objects.filter(id__in=instance_test_ids)
    for test in instance_test_list:
        instance_tests[test.id] = test
    # add the tests and other informations to each instance
    for instance in instances:
        if instance.last_test_id in instance_tests:
            instance.last_test = instance_tests[instance.last_test_id]
            if instance.last_test.connection_error_message != '':
                # connection problem
                instance.last_test.result_class = 'label-danger'
                instance.last_test.result_msg = instance.last_test.connection_error_message
            elif not instance.last_test.valid_instance and instance.last_test.http_status_code < 300:
                # connection is working and get HTTP response but there is no searx instance
                instance.last_test.result_class = 'label-danger'
                instance.last_test.result_msg = str(instance.last_test.http_status_code) + ' - Not a valid Searx instance'
            else:
                # connection ok, display HTTP error code
                instance.last_test.result_msg = str(instance.last_test.http_status_code) \
                + ' - ' + HTTP_CODE.get(instance.last_test.http_status_code, '')
                if instance.last_test.http_status_code < 300:
                    # valid instance because it was tested before
                    instance.last_test.result_class = 'label-success'
                elif instance.last_test.http_status_code < 400:
                    instance.last_test.result_class = 'label-warning'
                else:
                    instance.last_test.result_class = 'label-danger'
        else:
            #
            instance.last_test = {}
            instance.last_test['result_class'] = 'label-default'
            instance.last_test['result_msg'] = 'Untested'

    # rendering
    template = loader.get_template('stats/index.html')
    context = {
        'instances': instances,
    }
    return HttpResponse(template.render(context, request))


def instance(request, instance_id):
    instance = get_object_or_404(Instance, pk=instance_id)
    '''
    display:
    - history for normal instance and onion instance: certificate change, searx version change, url change
    how ?
    - load InstanceTest, iterate, and a new entry each time there a change

    display:
    - response time (avg, median, 95% quartile)
    '''
    return HttpResponse('')


def engine_list(request):
    return HttpResponse('')


def engine(request, instance):
    return HttpResponse('')
