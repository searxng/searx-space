import ssl
import httpx.config
import httpx.backends.asyncio
from OpenSSL.crypto import load_certificate, FILETYPE_ASN1
from searxstats.config import USE_SYSTEM_CERT


# ssl information cache
SSL_INFO = dict()
SSL_CERT = dict()


class SystemCertSSLConfig(httpx.config.SSLConfig):

    def __init__(self, *args, **kwargs):
        super(SystemCertSSLConfig, self).__init__(*args, **kwargs)

    def _load_client_certs(self, ssl_context: ssl.SSLContext) -> None:
        """
        Loads client certificates into our SSLContext object
        """
        ssl_context.load_default_certs()


def monkey_patch():
    original_start_tls = getattr(
        httpx.backends.asyncio.AsyncioBackend, 'open_tcp_stream')

    def concat_to_key(obj, key, value):
        if key in obj:
            obj[key] = obj[key] + ", " + value
        else:
            obj[key] = value

    def cert_to_obj(cert):
        obj = {
            "issuer": {},
            "subject": {},
        }
        for field in obj.keys():  # pylint: disable=consider-iterating-dictionary
            for field_values in cert.get(field, {}):
                for value in field_values:
                    concat_to_key(obj[field], value[0], value[1])
        for field in ['version', 'serialNumber', 'notBefore', 'notAfter', 'OCSP', 'caIssuers', 'crlDistributionPoints']:
            if field in cert:
                obj[field] = cert.get(field)
        return obj

    def parse_sslobject(sslobj: ssl.SSLObject):
        global SSL_INFO, SSL_CERT  # pylint: disable=global-statement
        if sslobj is None:
            return
        cert_dict = sslobj.getpeercert(binary_form=False)
        cert_bin = sslobj.getpeercert(binary_form=True)
        if sslobj.server_hostname not in SSL_INFO:
            SSL_INFO[sslobj.server_hostname] = {
                'version': sslobj.version(),
                'certificate': cert_to_obj(cert_dict)
            }
            # TODO python <= 3.6: convert IDN to ASCII
            SSL_CERT[sslobj.server_hostname] = cert_bin

    async def open_tcp_stream(*args, **kwargs):
        value = await original_start_tls(*args, **kwargs)
        sslobj = value.stream_reader._transport.get_extra_info('ssl_object')  # pylint: disable=protected-access
        parse_sslobject(sslobj)
        return value
    # monkey patch to record certificates
    setattr(httpx.backends.asyncio.AsyncioBackend, 'open_tcp_stream', open_tcp_stream)
    # use system certificate
    if USE_SYSTEM_CERT:
        httpx.config.DEFAULT_SSL_CONFIG = SystemCertSSLConfig(cert=None, verify=True)


def get_sslinfo(host):
    global SSL_INFO, SSL_CERT  # pylint: disable=global-statement
    ssl_obj = SSL_INFO.get(host, {})
    cert_bin = SSL_CERT.get(host, None)
    if cert_bin is not None and 'sha256' not in ssl_obj['certificate']:
        bincert = load_certificate(FILETYPE_ASN1, cert_bin)
        cert_obj = ssl_obj['certificate']
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
    return ssl_obj
