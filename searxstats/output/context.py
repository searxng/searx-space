import functools
import jinja2
from ..common.http import get_network_type, NetworkType
from ..model import SearxStatisticsResult


TOOLTIP_REQUESTS = 'tooltip_requests'
COMMON_ERROR_MESSAGE = {
    'Connection refused': 'Connection refused',
    'Connection timed out': 'Connection timed out',
    'HTTP status code 4': 'HTTP client error',
    'HTTP status code 5': 'HTTP server error',
    '[Errno -2] Name or service not known': 'Unknown host',
    '[Errno -2] Name does not resolve': 'Unknown host',
    'certificate verify failed': 'Certificate verify failed',
    'hostname \'': 'Hostname doesn\'t match certificate',
    'Tor Error: ': 'Tor Error'
}


def get_error_key(error_message):
    if isinstance(error_message, str):
        for error_prefix, message in COMMON_ERROR_MESSAGE.items():
            if error_message.startswith(error_prefix):
                return message
    return 'Others'


def add_tooltip(context: dict, tooltip_type: str, instance_id: str):
    context.setdefault(TOOLTIP_REQUESTS, dict())
    context[TOOLTIP_REQUESTS].setdefault(tooltip_type, list())
    context[TOOLTIP_REQUESTS][tooltip_type].append(context['instances_by_id'][instance_id])
    tooltip_id = 'tooltip' + '_' + instance_id + '_' + tooltip_type
    return f"data-tooltip=\"{tooltip_id}\" aria-describedby=\"{tooltip_id}\""


def tooltip_list(context: dict, tooltip_type: str):
    return context.get(TOOLTIP_REQUESTS, dict()).get(tooltip_type, list())


def get_context(searx_stats_result: SearxStatisticsResult, template: jinja2.Template):
    context = searx_stats_result.get_json()
    context['template'] = template.name
    template.environment.globals['add_tooltip'] = functools.partial(add_tooltip, context)
    template.environment.globals['tooltip_list'] = functools.partial(tooltip_list, context)

    instances_https = list()
    instances_tor = list()
    instances_withoutsearx = list()
    instances_error = dict()

    context['instances_https'] = instances_https
    context['instances_tor'] = instances_tor
    context['instances_withoutsearx'] = instances_withoutsearx
    context['instances_error'] = instances_error
    context['instances_by_id'] = dict()

    counter = 1

    for url, instance in searx_stats_result.instances.items():
        # add url and id
        instance['url'] = url
        instance['id'] = f'id{counter:03}'
        context['instances_by_id'][instance['id']] = instance
        counter += 1
        # set default
        instance.setdefault('network', {})
        instance.setdefault('tls', {})
        instance['tls'].setdefault('certificate', {})
        instance.setdefault('timing', {})
        instance['timing'].setdefault('index', {})
        instance['timing']['index'].setdefault('all', {})
        instance['timing'].setdefault('search_wp', {})
        instance['timing']['search_wp'].setdefault('all', {})
        instance['timing'].setdefault('search_go', {})
        instance['timing']['search_go'].setdefault('all', {})
        instance.setdefault('html', {})
        instance['html'].setdefault('grade', '')

        network_type = get_network_type(url)

        # dispatch instance between instances_https, instances_tor, instances_withoutsearx, instances_error
        if 'error' in instance and instance['error'] is not None:
            error_key = get_error_key(instance['error'])
            instances_error.setdefault(error_key, list())
            instances_error[error_key].append(instance)
        elif instance['version'] is None:
            instances_withoutsearx.append(instance)
        elif network_type == NetworkType.TOR:
            instances_tor.append(instance)
        elif network_type == NetworkType.NORMAL:
            instances_https.append(instance)
        else:
            # ??
            print('unknow network', url, instance)

    return context
