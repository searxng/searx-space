import ssl
import httpx
import httpx.config
import httpx.backends.asyncio
from OpenSSL.crypto import load_certificate, FILETYPE_ASN1


def set_or_concat_value(obj, key, value):
    if key in obj:
        obj[key] = obj[key] + ', ' + value
    else:
        obj[key] = value


def cert_to_obj(cert):
    obj = {}
    for field in ['issuer', 'subject']:
        obj[field] = {}
        for keys_values_for_cert_field in cert.get(field, {}):
            for cert_key_value in keys_values_for_cert_field:
                set_or_concat_value(obj[field], cert_key_value[0], cert_key_value[1])
    for field in ['version', 'serialNumber', 'notBefore', 'notAfter', 'OCSP', 'caIssuers', 'crlDistributionPoints']:
        if field in cert:
            obj[field] = cert.get(field)
    return obj


def update_obj_with_bin(cert_obj, cert_bin):
    bincert = load_certificate(FILETYPE_ASN1, cert_bin)
    cert_obj['sha256'] = bincert.digest('sha256').decode('utf-8')
    cert_obj['notAfter'] = bincert.get_notAfter().decode('utf-8')
    cert_obj['notBefore'] = bincert.get_notBefore().decode('utf-8')
    cert_obj['signatureAlgorithm'] = bincert.get_signature_algorithm().decode('utf-8')
    cert_obj['subject'] = {
        'commonName': bincert.get_subject().commonName,
        'countryName': bincert.get_subject().countryName,
        'organizationName': bincert.get_subject().organizationName,
    }
    cert_obj['issuer'] = {
        'commonName': bincert.get_issuer().commonName,
        'countryName': bincert.get_issuer().countryName,
        'organizationName': bincert.get_issuer().organizationName,
    }
    for i in range(0, bincert.get_extension_count()):
        ex = bincert.get_extension(i)
        if ex.get_short_name() == b'subjectAltName':
            cert_obj['subject']['altName'] = str(ex)


class SslInfo:

    __slots__ = ['_ssl_info']

    def __init__(self):
        self._ssl_info = dict()

    def parse_sslobject(self, hostname: str, sslobj: ssl.SSLObject):
        if sslobj is None:
            return
        if hostname not in self._ssl_info:
            cert_dict = sslobj.getpeercert(binary_form=False)
            cert_bin = sslobj.getpeercert(binary_form=True)
            # make cert_obj using cert_dict and cert_bin
            cert_obj = cert_to_obj(cert_dict)
            if cert_bin is not None and 'sha256' not in cert_obj:
                update_obj_with_bin(cert_obj, cert_bin)
            # store values
            self._ssl_info[hostname] = {
                'version': sslobj.version(),
                'certificate': cert_obj
            }

    def get(self, hostname: str):
        return self._ssl_info.get(hostname, {})


class AsyncioBackendLogCert(httpx.backends.asyncio.AsyncioBackend):

    __slots__ = ['_sslinfo']

    def __init__(self, sslinfo: SslInfo):
        super().__init__()
        self._sslinfo = sslinfo

    async def open_tcp_stream(self, hostname, port, ssl_context, timeout):
        value = await super().open_tcp_stream(hostname, port, ssl_context, timeout)
        sslobj = value.stream_reader._transport.get_extra_info('ssl_object')  # pylint: disable=protected-access
        self._sslinfo.parse_sslobject(hostname, sslobj)
        return value


SSLINFO = SslInfo()


def get_httpx_backend():
    global SSLINFO  # pylint: disable=global-statement
    return AsyncioBackendLogCert(SSLINFO)


def get_ssl_info(hostname):
    global SSLINFO  # pylint: disable=global-statement
    return SSLINFO.get(hostname)
