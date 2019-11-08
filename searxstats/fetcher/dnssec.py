import sys
import dns.name
import dns.query
import dns.dnssec
import dns.message
import dns.resolver
import dns.rdatatype


def get_nsaddr(hostname):
    # get nameservers for target domain
    response = dns.resolver.query(hostname, dns.rdatatype.NS)

    # we'll use the first nameserver in this example
    nsname = response.rrset[0].to_text()  # name
    response = dns.resolver.query(nsname, dns.rdatatype.A)
    nsaddr = response.rrset[0].to_text()  # IPv4
    return nsaddr


def get_rrset_rrsigset(nsaddr, hostname):
    # get DNSKEY for zone
    request = dns.message.make_query(hostname,
                                     dns.rdatatype.DNSKEY,
                                     want_dnssec=True)

    # send the query
    response = dns.query.udp(request, nsaddr)
    if response.rcode() != 0:
        # HANDLE QUERY FAILED (SERVER ERROR OR NO DNSKEY RECORD)
        print(response.rcode())
        sys.exit(1)

    # answer should contain two RRSET: DNSKEY and RRSIG(DNSKEY)
    answer = response.answer
    if len(answer) != 2:
        # SOMETHING WENT WRONG
        print(answer)
        sys.exit(1)

    return (answer[0], answer[1])


def validate(hostname):
    # get nameserver IP
    nsaddr = get_nsaddr(hostname)

    # get rrset and rrsigset
    rrset, rrsigset = get_rrset_rrsigset(nsaddr, hostname)

    print('rrset {} {}'.format(type(rrset), rrset))
    print('rrsigset {} {}'.format(type(rrsigset), rrsigset))

    # the DNSKEY should be self signed, validate it
    name = dns.name.from_text(hostname)
    try:
        dns.dnssec.validate(rrset, rrsigset, {name: rrset})
    except dns.dnssec.ValidationFailure as ex:
        # BE SUSPICIOUS
        print(ex)
        print('be suspicious')
    else:
        # WE'RE GOOD, THERE'S A VALID DNSSEC SELF-SIGNED KEY FOR example.com
        print('we are good')
        sys.exit(0)


validate('al-f.net.')
