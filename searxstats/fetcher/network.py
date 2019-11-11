import dns.resolver
import dns.reversename
import ipwhois
from searxstats.utils import get_host, exception_to_str
from searxstats.memoize import MemoizeToDisk
from searxstats.model import SearxStatisticsResult


ONE_DAY_IN_SECOND = 24*3600
ONE_WEEK_IN_SECOND = 7*24*3600


def is_valid(result):
    if isinstance(result, tuple):
        return result[1] is None and result[1] != ''
    return True


@MemoizeToDisk(expire_time=ONE_WEEK_IN_SECOND, validate_result=is_valid)
def get_whois(address):
    whois_error = None
    result = None
    obj = ipwhois.IPWhois(address)
    try:
        results = obj.lookup_rdap(depth=1)
    except ipwhois.exceptions.BaseIpwhoisException as ex:
        whois_error = exception_to_str(ex)
    else:
        country = results.get('network', {}).get('country', '') or results.get('asn_country_code', '')
        description = results.get('network', {}).get('name', ''), results.get('asn_description', '')
        result = [description, country.upper()]
    return result, whois_error


@MemoizeToDisk(expire_time=ONE_DAY_IN_SECOND, validate_result=is_valid)
def get_reverse(address):
    # TODO check if address must str
    reverse_error = None
    rev_name = dns.reversename.from_address(address)
    try:
        reverse_dns = str(dns.resolver.query(rev_name, 'PTR')[0])
    except dns.resolver.NXDOMAIN:
        # ignore not existing NXDOMAIN error
        reverse_dns = None
        reverse_error = None
    except dns.resolver.NoNameservers:
        reverse_dns = None
        reverse_error = 'NoNameservers'
    except dns.exception.Timeout:
        reverse_dns = None
        reverse_error = 'Timeout'
    except Exception as ex:
        reverse_dns = None
        reverse_error = exception_to_str(ex)
    return reverse_dns, reverse_error


def get_address_info(address):
    # TODO check if address must str
    address = str(address)
    whois_info, whois_info_error = get_whois(address)
    reverse_dns, reverse_dns_error = get_reverse(address)
    result = {
        'reverse': reverse_dns,
        'whois': whois_info
    }
    if reverse_dns_error is not None:
        result['error'] = reverse_dns_error
    elif whois_info_error is not None:
        result['error'] = whois_info_error
    return result


@MemoizeToDisk(expire_time=ONE_DAY_IN_SECOND)
def dns_resolve(host, field):
    try:
        answers = dns.resolver.query(host, field)
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        # No IPv6 (or IPv6) : that's okay.
        return [], None
    except Exception as ex:
        return [], exception_to_str(ex)
    else:
        return list(map(str, answers)), None


def get_network_info(host):
    result = {}
    for field_type in ['A', 'AAAA']:
        addresses, error = dns_resolve(host, field_type)
        if error is not None:
            result['error'] = error
        for address in addresses:
            result[str(address)] = get_address_info(address)
    return result


def fetch(searx_stats_result: SearxStatisticsResult):
    for url, detail in searx_stats_result.iter_all_instances():
        instance_host = get_host(url)
        network_detail = get_network_info(instance_host)
        print('🌏 {0:30} {1}'.format(instance_host, network_detail.get('error', '')))
        detail['network'] = network_detail
