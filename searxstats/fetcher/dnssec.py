# pylint: disable=invalid-name

# /!\ not functionnal

import dns.name
import dns.query
import dns.dnssec
import dns.message
import dns.resolver
import dns.rdatatype

from searxstats.model import create_fetch
from searxstats.common.http import get_host, NetworkType


class DnsSecError(Exception):
    pass


def get_nsaddr(resolver, hostname):
    print('get_nsaddr', hostname)
    # get nameservers for target domain
    response = resolver.query(hostname, dns.rdatatype.NS, raise_on_no_answer=False)
    if response is None or response.rrset is None:
        return get_nsaddr(resolver, hostname.parent())

    # use the first nameserver
    nsname = response.rrset[0].to_text()  # name
    response = resolver.query(nsname, dns.rdatatype.A)
    nsaddr = response.rrset[0].to_text()  # IPv4
    return nsaddr


def get_rrset_rrsigset(nsaddr, hostname):
    # get DNSKEY for zone
    request = dns.message.make_query(hostname,
                                     dns.rdatatype.DNSKEY,
                                     want_dnssec=True)

    # send the query
    response = dns.query.udp(request, nsaddr)
    print(response)
    if response.rcode() != 0:
        # HANDLE QUERY FAILED (SERVER ERROR OR NO DNSKEY RECORD)
        print(response.rcode())
        raise DnsSecError()

    # answer should contain two RRSET: DNSKEY and RRSIG(DNSKEY)
    answer = response.answer
    rrset = None
    rrsigset = None
    cname = None
    for a in answer:
        if a.rdtype == 48:
            rrset = a
        elif a.rdtype == 46:
            rrsigset = a
        elif a.rdtype == 5:
            cname = a

    if rrset is not None and rrsigset is not None:
        return (rrset, rrsigset, cname)
    else:
        raise DnsSecError()


def validate(hostname):
    resolver = dns.resolver.Resolver()
    resolver.timeout = 10
    resolver.lifetime = 10

    # get nameserver IP
    nsaddr = get_nsaddr(resolver, dns.name.from_text(hostname))

    # get rrset and rrsigset
    try:
        rrset, rrsigset, _ = get_rrset_rrsigset(nsaddr, hostname)
    except DnsSecError:
        return "No DNSSEC"

    # the DNSKEY should be self signed, validate it
    name = dns.name.from_text(hostname)
    try:
        dns.dnssec.validate(rrset, rrsigset, {name: rrset})
    except dns.dnssec.ValidationFailure as ex:
        # BE SUSPICIOUS
        print(ex)
        return False
    else:
        # WE'RE GOOD, THERE'S A VALID DNSSEC SELF-SIGNED KEY FOR example.com
        return True


def fetch_one(url: str) -> dict:
    instance_host = get_host(url)
    dnssec_result = validate(instance_host)
    print('🌏 {0:30} {1}'.format(instance_host, dnssec_result))
    return dnssec_result


fetch = create_fetch(['network', 'dnssec'], fetch_one, only_valid=False, network_type=NetworkType.NORMAL)
