# pylint: disable=invalid-name
import datetime
import os
from functools import cmp_to_key
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader


_ERROR_TITLES = (
    ('Connection refused', 'Connection refused'),
    ('Connection timed out', 'Connection timed out'),
    ('HTTP status code 4', 'HTTP client error'),
    ('HTTP status code 5', 'HTTP server error'),
    ('[Errno -2] Name or service not known', 'Unknown host'),
    ('[Errno -2] Name does not resolve', 'Unknown host'),
    ('certificate verify failed', 'Certificate verify failed'),
    ("hostname '", "Hostname doesn't match certificate"),
    ('Tor Error: ', 'Tor Error'),
)

_HTML_RANK = {'V': 3, 'F': 3, 'C': 3, 'Cjs': 3, 'E': 0, '👁️': 0}
_HTML_LABEL = {
    'V': 'Vanilla',
    'F': 'Fork',
    'C': 'Customized, vanilla Javascript',
    'Cjs': 'Customized, including Javascript',
    'E': 'External resources',
    '👁️': 'Analytics',
    '?': 'Unknow',
    'js?': 'Unloaded Javascript',
}
_TIME_KEYS = ('all', 'server', 'load', 'network', 'processing')
_DNSSEC = {0: 'Unknow', 1: 'Secure', 2: 'Insecure', 3: 'Bogus'}
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=True,
    finalize=lambda value: value if value is not None else '',
)


def _error_title(message):
    if isinstance(message, str):
        for prefix, title in _ERROR_TITLES:
            if message.startswith(prefix):
                return title
    return 'Others'


def _version(detail):
    version = detail.get('version')
    return version.split(' ')[0] if isinstance(version, str) else version


def _translate(value, from_min, from_max, to_min, to_max, reverse=False):
    valuei = max(from_min, min(float(value), from_max)) - from_min
    valuem = round((valuei * (to_max - to_min)) / (from_max - from_min))
    return to_max - valuem if reverse else valuem + to_min


def _hsl_ramp(value, vmax):
    value = min(vmax, max(0, value))
    return 'hsl({}, {}%, 54%)'.format(
        _translate(value, 0, vmax, 0, 128),
        _translate(value, 0, vmax, 39, 54, True),
    )


def _hsl_unknown():
    return 'hsl(0, 0%, 74%)'


def _html_rank(grade):
    return _HTML_RANK.get((grade or '').split(',')[0].strip(), -1)


def _normalize_grade(grade):
    if not grade or grade == '?':
        return -1
    result = (ord('G') - ord(str(grade)[0])) * 3 + 1
    if len(grade) == 2 and grade.endswith('+'):
        return result + 1
    if len(grade) == 2 and grade.endswith('-'):
        return result - 1
    return result


def _hsl_grade(grade):
    if grade in (-1, '?', '', None):
        return _hsl_unknown()
    normalized = _normalize_grade(grade)
    if normalized == -1:
        return _hsl_unknown()
    return _hsl_ramp(normalized - 3, 17)


def _hsl_html(grade):
    ngrade = _html_rank(grade)
    return _hsl_unknown() if ngrade == -1 else _hsl_ramp(ngrade, 3)


def _hsl_response_time(value, success_rate):
    if value == 'N/A':
        value = 2
    shown = (_translate(value, 0.6, 2.5, 0, 100, True) / 100) * (
        _translate(100 if success_rate is None else success_rate, 70, 100, 0, 100) / 100
    ) * 100
    return _hsl_ramp(shown, 100)


def _hsl_uptime(percentage):
    step = min(100, max(90, percentage)) - 90
    return _hsl_ramp(step * step, 100)


def _get(detail, *keys):
    value = detail
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _cmp_desc(va, vb):
    if va == vb:
        return 0
    if va == '' or vb == '':
        return 1 if va == '' else -1
    if va is None or vb is None:
        return -1 if va is None else 1
    try:
        return (va < vb) - (va > vb)
    except TypeError:
        return 0


def _uptime_n(detail):
    month = _get(detail, 'uptime', 'uptimeMonth')
    return round(month / 5) * 5 if isinstance(month, (int, float)) else -1


def _searx_version_key(version):
    if not isinstance(version, str):
        return (0, 0, 0)
    head = version.replace('+', '-').split('-', 1)[0]
    try:
        year, month, day = (int(part) for part in head.split('.'))
        parsed = datetime.date(year, month, day)
    except ValueError:
        parsed = None
    if parsed is not None and parsed.year >= 2020:
        now = datetime.date.today()
        month_diff = max(0, (now.year - parsed.year) * 12 + (now.month - parsed.month))
        return (10000 - (0 if month_diff < 2 else month_diff), 0, 0)
    nums = []
    for part in head.split('.')[:3]:
        try:
            nums.append(int(part))
        except ValueError:
            nums.append(0)
    return tuple((nums + [0, 0, 0])[:3])


def _is_error(timing):
    pct = (timing or {}).get('success_percentage')
    if isinstance(pct, (int, float)) and pct < 100:
        return 100 - pct
    return 100 if (timing or {}).get('error') else 0


def _get_time(timing):
    if not isinstance(timing, dict):
        return None
    if 'value' in timing:
        return timing['value']
    return timing.get('median')


def _cmp_instances(left, right):
    ua, a = left
    ub, b = right

    def search(detail):
        return _get(detail, 'timing', 'search') or {}

    def search_go(detail):
        return _get(detail, 'timing', 'search_go') or {}

    keys = (
        (True, _get(a, 'http', 'status_code'), _get(b, 'http', 'status_code')),
        (True, a.get('error'), b.get('error')),
        (False, _html_rank(_get(a, 'html', 'grade')), _html_rank(_get(b, 'html', 'grade'))),
        (True, _is_error(search(a)), _is_error(search(b))),
        (False, _normalize_grade(_get(a, 'tls', 'grade') or '?'),
         _normalize_grade(_get(b, 'tls', 'grade') or '?')),
        (False, _normalize_grade(_get(a, 'http', 'grade') or '?'),
         _normalize_grade(_get(b, 'http', 'grade') or '?')),
        (False, _uptime_n(a), _uptime_n(b)),
        (False, _searx_version_key(_version(a)), _searx_version_key(_version(b))),
        (False, min(search(a).get('working_engines') or 0, 3),
         min(search(b).get('working_engines') or 0, 3)),
        (True, _is_error(search_go(a)), _is_error(search_go(b))),
        (True, _get_time(_get(a, 'timing', 'search', 'all') or {}),
         _get_time(_get(b, 'timing', 'search', 'all') or {})),
        (True, _get_time(_get(a, 'timing', 'search_go', 'all') or {}),
         _get_time(_get(b, 'timing', 'search_go', 'all') or {})),
        (True, ua, ub),
    )
    for asc, va, vb in keys:
        result = -_cmp_desc(va, vb) if asc else _cmp_desc(va, vb)
        if result:
            return result
    return 0


_INSTANCE_SORT = cmp_to_key(_cmp_instances)


def _js_num(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_time(value):
    return f'{value:.3f}' if isinstance(value, (int, float)) else value


def _notes(detail):
    return {
        'comments': detail.get('comments') or [],
        'alts': list((detail.get('alternativeUrls') or {}).items()),
    }


def _url_view(url, detail):
    notes = _notes(detail)
    contact = detail.get('contact_url')
    label = None
    if contact:
        label = contact[7:] if contact.lower().startswith('mailto:') else contact
    return {
        'href': url,
        **notes,
        'git_url': detail.get('git_url'),
        'contact': contact,
        'contact_label': label,
        'has_tip': bool(notes['comments'] or notes['alts'] or detail.get('git_url') or contact),
    }


def _grade_view(grade, href=None, color=None, tooltip=None, tip_rows=None):
    if grade is None:
        return None
    return {
        'grade': grade,
        'href': href,
        'color': color or _hsl_grade(grade),
        'tooltip': tooltip,
        'tip_rows': tip_rows,
    }


def _tls_view(tls):
    tls = tls or {}
    grade = tls.get('grade')
    if grade is None:
        return None
    return _grade_view(grade, tls.get('gradeUrl'), tooltip=tls.get('version') or None)


def _csp_view(http):
    http = http or {}
    grade = http.get('grade')
    if grade is None:
        return None
    score = http.get('score')
    tooltip = f'Score {score}' if score is not None else None
    return _grade_view(grade, http.get('gradeUrl'), tooltip=tooltip)


def _html_view(html, git_url):
    grade = (html or {}).get('grade') or '?'
    label = _HTML_LABEL.get(str(grade).split(',', maxsplit=1)[0], '')
    tip_rows = []
    if label:
        tip_rows.append([label])
    if git_url:
        tip_rows.append(['Git URL', {'href': git_url, 'text': git_url}])
    return _grade_view(grade, color=_hsl_html(grade), tip_rows=tip_rows or None)


def _cert_view(url, tls):
    cert = ((tls or {}).get('certificate') or {})
    issuer = cert.get('issuer') or {}
    if not issuer:
        return None
    org = issuer.get('organizationName') or issuer.get('commonName') or ''
    country = issuer.get('countryName') or ''
    subject = cert.get('subject') or {}
    return {
        'href': 'https://crt.sh/?q=' + (urlparse(url).hostname or ''),
        'text': f'{org} ({country})' if country else org,
        'tip_rows': [
            [{'bold': 'Subject'}],
            ['Name', subject.get('commonName')],
            ['AltName', subject.get('altName')],
            ['Country', subject.get('countryName')],
            ['Organization', subject.get('organizationName')],
            [{'bold': 'Issuer'}],
            ['Name', issuer.get('commonName')],
            ['Country', issuer.get('countryName')],
            ['Organization', issuer.get('organizationName')],
            [{'bold': 'Validity'}],
            ['From', cert.get('notBefore')],
            ['To', cert.get('notAfter')],
            [{'bold': 'Fingerprint'}],
            ['Serial number', cert.get('serialNumber')],
            ['SHA256', cert.get('sha256')],
        ],
    }


def _netinfo(detail, cidrs):
    network = detail.get('network') or {}
    countries, names, privacy_vals, hosts = [], [], [], []
    for ip, ipinfo in (network.get('ips') or {}).items():
        if not isinstance(ipinfo, dict):
            ipinfo = {}
        host = ipinfo.get('reverse') or ip
        if host not in hosts:
            hosts.append(host)
        asn = (cidrs or {}).get(ipinfo.get('asn_cidr') or '')
        if not asn:
            continue
        country = asn.get('network_country') or asn.get('asn_country_code')
        if country and country not in countries:
            countries.append(country)
        name = asn.get('asn_description')
        if name and name not in names:
            names.append(name)
        if 'asn_privacy' in asn:
            privacy_vals.append(asn['asn_privacy'])
    if 'asn_privacy' in network:
        privacy = network['asn_privacy']
    else:
        privacy = min(privacy_vals) if privacy_vals else 0
    dnssec = network.get('dnssec') or 0
    netname = ', '.join(names)
    mark = ' ❗' if dnssec == 3 else ''
    grade = {-1: 'F-', 1: 'A+'}.get(privacy) or ('D-' if dnssec == 3 else None)
    return {
        'country': ', '.join(countries),
        'name': netname,
        'privacy': privacy,
        'ipv6': network.get('ipv6'),
        'text': netname + mark,
        'color': _hsl_grade(grade) if grade else None,
        'dnssec': (_DNSSEC.get(dnssec, '') + mark) if dnssec else '',
        'hosts': hosts,
    }


def _sub_time(left, right, field):
    a, b = (left or {}).get(field), (right or {}).get(field)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a - b or None
    return None


def _with_derived_times(timing):
    timing = dict(timing or {})
    all_t, server, load = timing.get('all'), timing.get('server'), timing.get('load')
    if server and all_t:
        timing['network'] = {
            'median': _sub_time(all_t, server, 'median'),
            'value': _sub_time(all_t, server, 'value'),
        }
    if load and server:
        timing['processing'] = {
            'median': _sub_time(server, load, 'median'),
            'value': _sub_time(server, load, 'value'),
        }
    return timing


def _bucket_value(timing, key):
    bucket = timing.get(key) or {}
    value = bucket.get('median', bucket.get('value'))
    if value is None and timing.get('error'):
        return 'Error'
    return value


def _time_view(timing):
    timing = _with_derived_times(timing)
    if not timing or (timing.get('error') == 'No result' and timing.get('success_percentage') == 0):
        return None
    times = {}
    success = timing.get('success_percentage')
    for key in _TIME_KEYS:
        value = _bucket_value(timing, key)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            times[key] = [_format_time(value), _hsl_response_time(value, success)]
        else:
            times[key] = [str(value), '']
    default = times.get('all') or ['', '']
    count = timing.get('working_engines')
    engines = None
    if count is not None:
        names = timing.get('working_engine_names') or []
        label = 'No engines' if count < 1 else f'{count} engine' + ('' if count == 1 else 's')
        grade = ['F', 'E', 'D'][count] if isinstance(count, int) and 0 <= count < 3 else None
        engines = {
            'text': f'{label}: {", ".join(names)}' if names else label,
            'color': _hsl_grade(grade) if grade else None,
        }
    lines = []
    for key, label in (('all', 'Total time'), ('server', 'Server time'), ('load', 'Load time')):
        median = (timing.get(key) or {}).get('median', (timing.get(key) or {}).get('value'))
        if median is not None:
            lines.append((label, _format_time(median)))
    return {
        'times': times,
        'text': default[0],
        'color': default[1],
        'success': _js_num(success) if success is not None else None,
        'engines': engines,
        'error': timing.get('error'),
        'lines': lines,
    }


def _uptime_view(url, uptime):
    if not uptime or not isinstance(uptime.get('uptimeMonth'), (int, float)):
        return None
    host = (urlparse(url).hostname or '').replace('.', '-')
    month = int(round(uptime['uptimeMonth']))
    return {
        'href': 'https://uptime.searxng.org/history/' + host,
        'text': f'{month} %',
        'color': _hsl_uptime(uptime['uptimeMonth']),
        'day': int(round(uptime.get('uptimeDay') or 0)),
        'week': int(round(uptime.get('uptimeWeek') or 0)),
        'month': month,
        'year': int(round(uptime.get('uptimeYear') or 0)),
    }


def _status_view(status):
    if status is None:
        return None
    try:
        code = int(status)
    except (TypeError, ValueError):
        return {'text': str(status), 'css': None}
    if 200 <= code < 300:
        css = 'label-success'
    elif 300 <= code < 400:
        css = 'label-warning'
    else:
        css = 'label-danger'
    return {'text': str(code), 'css': css}


def _https_row(url, detail, net):
    html = detail.get('html') or {}
    timing = detail.get('timing') or {}
    version = _version(detail) or ''
    ipv6 = net['ipv6']
    return {
        'url': _url_view(url, detail),
        'version': version,
        'tls': _tls_view(detail.get('tls')),
        'csp': _csp_view(detail.get('http')),
        'html': _html_view(html, detail.get('git_url')),
        'cert': _cert_view(url, detail.get('tls')),
        'ipv6': {
            'text': 'Yes' if ipv6 is True else 'No' if ipv6 is False else '?',
            'color': _hsl_grade('F-') if ipv6 is False else None,
        },
        'country': net['country'],
        'network': net,
        'search': _time_view(timing.get('search')),
        'google': _time_view(timing.get('search_go')),
        'initial': _time_view(timing.get('initial')),
        'uptime': _uptime_view(url, detail.get('uptime')),
        'notes': _notes(detail),
        'filters': {
            'version': version,
            'tls': (detail.get('tls') or {}).get('grade') or '',
            'csp': (detail.get('http') or {}).get('grade') or '',
            'html': html.get('grade') or '',
            'ipv6': '1' if ipv6 is True else '0',
            'country': net['country'],
            'network': net['name'],
            'search': '1' if (timing.get('search') or {}).get('success_percentage') else '0',
            'google': '1' if (timing.get('search_go') or {}).get('success_percentage') else '0',
            'asn_privacy': net['privacy'],
        },
    }


def _tor_row(url, detail):
    timing = detail.get('timing') or {}
    return {
        'url': _url_view(url, detail),
        'version': _version(detail) or '',
        'html': _html_view(detail.get('html') or {}, detail.get('git_url')),
        'search': _time_view(timing.get('search')),
        'google': _time_view(timing.get('search_go')),
        'initial': _time_view(timing.get('initial')),
        'notes': _notes(detail),
    }


def _error_row(url, detail, with_error=False):
    return {
        'url': _url_view(url, detail),
        'status': _status_view((detail.get('http') or {}).get('status_code')),
        'error': detail.get('error') if with_error else None,
        'notes': _notes(detail),
    }


def _split(result):
    https, tor, nosearx, errors = [], [], [], {}
    for url, detail in result.instances.items():
        if detail.get('error'):
            errors.setdefault(_error_title(detail['error']), []).append((url, detail))
        elif _version(detail):
            (tor if detail.get('network_type') == 'tor' else https).append((url, detail))
        else:
            nosearx.append((url, detail))
    for group in (https, tor, nosearx, *errors.values()):
        group.sort(key=_INSTANCE_SORT)
    return https, tor, nosearx, errors


def render_html(result):
    https, tor, nosearx, errors = _split(result)
    cidrs = result.cidrs
    return _ENV.get_template('index.html').render(
        https=[_https_row(url, detail, _netinfo(detail, cidrs)) for url, detail in https],
        tor=[_tor_row(url, detail) for url, detail in tor],
        nosearx=[_error_row(url, detail) for url, detail in nosearx],
        errors=[
            (title, [_error_row(url, detail, with_error=True) for url, detail in rows])
            for title, rows in sorted(errors.items())
        ],
    )


def write_html(result, output_file_name):
    folder = os.path.dirname(os.path.abspath(output_file_name)) or '.'
    if os.path.basename(folder) == 'data':
        folder = os.path.dirname(folder)
    with open(os.path.join(folder, 'index.html'), 'w', encoding='utf-8') as output_file:
        output_file.write(render_html(result))


if __name__ == '__main__':
    import json
    import sys
    from types import SimpleNamespace
    _path = sys.argv[1]
    with open(_path, encoding='utf-8') as _f:
        write_html(SimpleNamespace(**json.load(_f)), _path)
