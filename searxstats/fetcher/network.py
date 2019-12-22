# pylint: disable=invalid-name
import socket
import dns.resolver
import dns.reversename
import ipwhois
from searxstats.data.asn import ASN_PRIVACY
from searxstats.common.utils import exception_to_str
from searxstats.common.http import get_host, get, new_session, NetworkType
from searxstats.common.memoize import MemoizeToDisk
from searxstats.common.foreach import for_each
from searxstats.model import SearxStatisticsResult, AsnPrivacy


HTTPS_PORT = 443
ONE_DAY_IN_SECOND = 24*3600
ONE_WEEK_IN_SECOND = 7*24*3600

URL_IPV4 = 'http://ipv4.whatismyip.akamai.com/'
URL_IPV6 = 'http://ipv6.whatismyip.akamai.com/'


def valid_if_no_error(result):
    if isinstance(result, tuple):
        return result[1] is None
    return True


def dns_query(qname, field):
    dns_answers = None
    dns_error = None
    try:
        dns_answers = dns.resolver.query(qname, field)
    except dns.resolver.NXDOMAIN:
        # ignore: The DNS query name does not exist.
        dns_answers = None
        dns_error = None
    except dns.resolver.NoAnswer:
        # ignore: The DNS response does not contain an answer to the question.
        dns_answers = None
        dns_error = None
    except dns.resolver.NoNameservers:
        # All nameservers failed to answer the query.
        # dns_error='No non-broken nameservers are available to answer the question'
        dns_answers = None
        dns_error = None
    except dns.exception.Timeout:
        # The DNS operation timed out.
        dns_answers = None
        dns_error = 'Timeout'
    except dns.resolver.YXDOMAIN:
        # The DNS query name is too long after DNAME substitution.
        dns_answers = None
        dns_error = 'Timeout after DNAME substitution'
    except Exception as ex:
        dns_answers = None
        dns_error = exception_to_str(ex)
    return dns_answers, dns_error


@MemoizeToDisk(expire_time=ONE_DAY_IN_SECOND, validate_result=valid_if_no_error)
def dns_query_field(host: str, field: str):
    """
    string everywhere to allow @MemoizeToDisk

    Equivalent of dns.resolver.query(qname, field)

    No exception

    returns (list of string, error_msg)

    list of string is the answers convert to string, empty list if there is an error

    error_msg is a text message that can be display to the user
    """
    dns_answers, dns_error = dns_query(host, field)
    return list(map(str, dns_answers or [])), dns_error


@MemoizeToDisk(expire_time=ONE_DAY_IN_SECOND, validate_result=valid_if_no_error)
def dns_query_reverse(address):
    """
    string everywhere to allow @MemoizeToDisk

    Equivalent of dns_query(dns.reversename.from_address(address), 'PTR')[0]

    No exception

    returns (reverse_name, error_msg)

    reverse_name None if there is an error

    error_msg is a text message that can be display to the user
    """
    reverse_dns = None
    reverse_error = None
    try:
        rev_name = dns.reversename.from_address(address)
    except dns.exception.SyntaxError:
        # shouldn't happen
        reverse_dns = None
        reverse_error = 'Invalid address'
    else:
        reverse_answer, reverse_error = dns_query(rev_name, 'PTR')
        if reverse_answer is not None:
            reverse_dns = str(reverse_answer[0])
    return reverse_dns, reverse_error


def safe_upper(o):
    if isinstance(o, str):
        return o.upper()
    return o


@MemoizeToDisk(expire_time=ONE_WEEK_IN_SECOND, validate_result=valid_if_no_error)
def get_whois(address: str):
    whois_error = None
    result = None
    obj = ipwhois.IPWhois(address)
    try:
        rdap_answer = obj.lookup_rdap(depth=1)
    except ipwhois.exceptions.BaseIpwhoisException as ex:
        whois_error = exception_to_str(ex)
    else:
        result = {
            'asn': rdap_answer.get('asn', ''),
            'asn_description': rdap_answer.get('asn_description', ''),
            'asn_country_code': safe_upper(rdap_answer.get('asn_country_code')),
            'asn_registry': rdap_answer.get('asn_registry', ''),
            'network_name': rdap_answer.get('network', {}).get('name', ''),
            'network_country': safe_upper(rdap_answer.get('network', {}).get('country', '')),
            'network_type': rdap_answer.get('network', {}).get('type', ''),
        }
        asn_privacy = ASN_PRIVACY.get(result['asn'], AsnPrivacy.UNKNOWN)
        if asn_privacy is not None:
            result['asn_privacy'] = asn_privacy.value
    return result, whois_error


@MemoizeToDisk(expire_time=ONE_DAY_IN_SECOND)
def check_https_port(address: str):
    try:
        sock = socket.create_connection((address, HTTPS_PORT), 5)
        sock.close()
        return True, None
    except Exception as ex:
        return False, exception_to_str(ex)


def get_address_info(searx_stats_result: SearxStatisticsResult, address: str, field_type: str, https_port: bool):
    reverse_dns, reverse_dns_error = dns_query_reverse(address)
    whois_info, whois_info_error = get_whois(address)

    result = {
        'reverse': reverse_dns,
        'field_type': field_type,
    }

    if whois_info is not None:
        asn = whois_info['asn']
        del whois_info['asn']
        result['asn'] = asn
        searx_stats_result.asns[asn] = whois_info

    if reverse_dns_error is not None:
        result['reverse_error'] = reverse_dns_error
    if whois_info_error is not None:
        result['whois_error'] = whois_info_error

    # check https ports
    if https_port:
        https_port, https_port_error = check_https_port(address)
        result['https_port'] = https_port
        if https_port_error is not None:
            result['https_port_error'] = https_port_error

    return result


def get_network_info(searx_stats_result: SearxStatisticsResult, host: str):
    result = {
        'ips': {},
        'ipv6': False,
        'asn_privacy': AsnPrivacy.UNKNOWN.value,
    }

    if searx_stats_result.metadata['ipv6']:
        field_type_list = ['A', 'AAAA']
    else:
        field_type_list = ['A']
        result['ipv6'] = None

    for field_type in field_type_list:
        addresses, error = dns_query_field(host, field_type)
        if error is not None:
            result['error'] = error
        if addresses is not None:
            for address in addresses:
                result['ips'][address] = get_address_info(searx_stats_result, address, field_type, True)
                if field_type == 'AAAA' and result['ips'][address]['https_port']:
                    # ipv6 support if at least one IPv6 address has the port 443 opened.
                    result['ipv6'] = True
                asn = result['ips'][address].get('asn')
                if asn is not None:
                    asn_privacy = searx_stats_result.asns.get(asn, {}).get('asn_privacy', AsnPrivacy.GOOD.value)
                    result['asn_privacy'] = min(asn_privacy, result['asn_privacy'])
    return result


def fetch_one(searx_stats_result: SearxStatisticsResult, url: str, detail):
    instance_host = get_host(url)
    network_detail = get_network_info(searx_stats_result, instance_host)
    detail['network'] = network_detail
    print('🌏 {0:30} {1}'.format(instance_host, network_detail.get('error', '')))


async def _fetch_network(searx_stats_result: SearxStatisticsResult):
    await for_each(searx_stats_result.iter_instances(only_valid=False, network_type=NetworkType.NORMAL),
                   fetch_one, searx_stats_result)


async def _find_similar_instances(searx_stats_result: SearxStatisticsResult):
    # group instance urls per ip set
    all_ips_set = dict()
    for url, detail in searx_stats_result.iter_instances(only_valid=False, network_type=NetworkType.NORMAL):
        ips = set(detail.get('network', {}).get('ips', {}).keys())
        # at least one IP
        if len(ips) > 0:
            # frozenset so it can use as a key of app_ips_set
            ips = frozenset(ips)
            urls = all_ips_set.setdefault(ips, set())
            urls.add(url)
    # set alternativeUrls
    for ips, urls in all_ips_set.items():
        if len(urls) > 1:
            # only if there are two or more instances sharing the same ips
            for url in urls:
                # for each url, create a reference to all other urls
                detail = searx_stats_result.get_instance(url)
                if 'alternativeUrls' not in detail:
                    detail['alternativeUrls'] = dict()

                for url2 in urls:
                    if url2 != url:
                        detail['alternativeUrls'][url2] = 'sameIps'


async def _check_connectivity(searx_stats_result: SearxStatisticsResult):
    async def get_ip(url):
        async with new_session() as session:
            response, error = await get(session, url)
        if error is None:
            return response.text, None
        else:
            return False, error
    ipv4, ipv4_error = await get_ip(URL_IPV4)
    ipv6, ipv6_error = await get_ip(URL_IPV6)
    searx_stats_result.metadata['ips'] = {}
    if ipv4:
        searx_stats_result.metadata['ips'][ipv4] = get_address_info(searx_stats_result, ipv4, 'A', False)
    else:
        print('⚠️ No IPv4 connectivity ', ipv4_error)
    if ipv6:
        searx_stats_result.metadata['ips'][ipv6] = get_address_info(searx_stats_result, ipv6, 'AAAA', False)
        searx_stats_result.metadata['ipv6'] = True
    else:
        searx_stats_result.metadata['ipv6'] = False
        print('⚠️ No IPv6 connectivity ', ipv6_error)


async def fetch(searx_stats_result: SearxStatisticsResult):
    await _check_connectivity(searx_stats_result)
    await _fetch_network(searx_stats_result)
    await _find_similar_instances(searx_stats_result)
