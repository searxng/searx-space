from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
from django.template import loader
from django.db.models import Count, Max

from .models import Instance, Engine, Query, InstanceTest

HTTP_CODE = {
    200: 'OK',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
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
    instances = Instance.objects.annotate(last_test_id=Max('instancetest')).order_by('install_since')
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
            if instance.last_test.error_message != '':
                instance.last_test.http_result_class = 'label-danger'
                instance.last_test.http_result_msg = instance.last_test.error_message
            else:
                instance.last_test.http_result_msg = str(instance.last_test.http_result) + ' - ' + HTTP_CODE.get(instance.last_test.http_result, '')
                if instance.last_test.http_result < 300:
                    instance.last_test.http_result_class = 'label-success'
                elif instance.last_test.http_result < 400:
                    instance.last_test.http_result_class = 'label-warning'
                else:
                    instance.last_test.http_result_class = 'label-danger'

    # rendering
    template = loader.get_template('stats/index.html')
    context = {
        'instances': instances,
    }
    return HttpResponse(template.render(context, request))


def instance(request, instance):
    return HttpResponse('')


def engine_list(request):
    return HttpResponse('')


def engine(request, instance):
    return HttpResponse('')

