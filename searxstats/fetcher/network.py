# pylint: disable=invalid-name
import dns.resolver
import dns.reversename
import ipwhois
from searxstats.common.utils import exception_to_str
from searxstats.common.http import get_host
from searxstats.common.memoize import MemoizeToDisk
from searxstats.model import create_fetch, SearxStatisticsResult


ONE_DAY_IN_SECOND = 24*3600
ONE_WEEK_IN_SECOND = 7*24*3600


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
        asn = rdap_answer.get('asn', '')
        name = rdap_answer.get('network', {}).get('name', '')
        description = rdap_answer.get('asn_description', '')
        country = rdap_answer.get('network', {}).get('country', '') or rdap_answer.get('asn_country_code', '')
        result = [name, description, country.upper(), asn]
    return result, whois_error


def get_address_info(address: str):
    reverse_dns, reverse_dns_error = dns_query_reverse(address)
    whois_info, whois_info_error = get_whois(address)
    result = {
        'reverse': reverse_dns,
        'whois': whois_info
    }
    if reverse_dns_error is not None:
        result['error'] = reverse_dns_error
    elif whois_info_error is not None:
        result['error'] = whois_info_error
    return result


def get_network_info(host: str):
    result = {}
    for field_type in ['A', 'AAAA']:
        addresses, error = dns_query_field(host, field_type)
        if error is not None:
            result['error'] = error
        if addresses is not None:
            for address in addresses:
                result[address] = get_address_info(address)
    return result


def fetch_one(url: str) -> dict:
    instance_host = get_host(url)
    network_detail = get_network_info(instance_host)
    print('🌏 {0:30} {1}'.format(instance_host, network_detail.get('error', '')))
    return network_detail


_fetch_network = create_fetch(['network'], fetch_one)


async def _find_similar_instances(searx_stats_result: SearxStatisticsResult):
    # group instance urls per ip set
    all_ips_set = dict()
    for url, detail in searx_stats_result.iter_instances(False):
        ips = set(detail['network'].keys())
        # ignore error field
        if 'error' in ips:
            ips.remove('error')
        # at least one IP
        if len(ips) > 0:
            # frozenset so it can use as a key of app_ips_set
            ips = frozenset(ips)
            urls = all_ips_set.setdefault(ips, set())
            urls.add(url)
    # set alternativeUrls
    for ips, urls in all_ips_set.items():
        if len(urls) > 1:
            # only if there are two instance sharing the same ips
            for url in urls:
                # for each url, create a reference to all other urls
                detail = searx_stats_result.get_instance(url)
                if 'alternativeUrls' not in detail:
                    detail['alternativeUrls'] = dict()

                for url2 in urls:
                    if url2 != url:
                        detail['alternativeUrls'][url2] = 'sameIps'


async def fetch(searx_stats_result: SearxStatisticsResult):
    await _fetch_network(searx_stats_result)
    await _find_similar_instances(searx_stats_result)
