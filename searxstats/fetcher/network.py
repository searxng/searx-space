import dns.resolver
import dns.reversename
import ipwhois
from searxstats.utils import get_host
from searxstats.memoize import MemoizeToDisk


@MemoizeToDisk()
def get_whois(address):
    obj = ipwhois.IPWhois(address)
    try:
        results = obj.lookup_rdap(depth=1)
    except ipwhois.exceptions.ASNRegistryError:
        return None
    else:
        country = results.get('network', {}).get('country', '') or results.get('asn_country_code', None)
        return [results.get('network', {}).get('name', ''), results.get('asn_description', ''), country]


def get_address_info(address):
    address = str(address)
    rev_name = dns.reversename.from_address(address)
    reverse_error = None
    try:
        reversed_dns = str(dns.resolver.query(rev_name, "PTR")[0])
    except dns.resolver.NXDOMAIN:
        # ignore not existing NXDOMAIN error
        reversed_dns = None
        reverse_error = None
    except dns.resolver.NoNameservers:
        reversed_dns = None
        reverse_error = 'NoNameservers'
    except dns.exception.Timeout:
        reversed_dns = None
        reverse_error = 'Timeout'
    except Exception as ex:
        reversed_dns = None
        reverse_error = str(ex)
    whois_info = get_whois(address)

    result = {
        'reverse': reversed_dns,
        'whois': whois_info
    }
    if reverse_error is not None:
        result['error'] = reverse_error
    return result


def get_reverse_dns(host, field):
    reverses = dict()
    try:
        answers = dns.resolver.query(host, field)
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        pass
    except Exception as ex:
        reverses['error'] = str(ex)
    else:
        for address in answers:
            print(' ' + str(address), end=' ', flush=True)
            reverses[str(address)] = get_address_info(address)
    print(reverses.get('error', ''), end='')
    return reverses


def get_reverse_dns_host(host):
    print('🌏 ' + host, end='')
    result = get_reverse_dns(host, 'A')
    result.update(get_reverse_dns(host, 'AAAA'))
    print('')
    return result


def fetch(searx_json):
    instance_details = searx_json['instances']
    for url in instance_details:
        instance_details[url]['network'] = get_reverse_dns_host(get_host(url))
