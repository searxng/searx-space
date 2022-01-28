import ssl
from typing import Dict
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


SSL_CONTEXT = ssl.create_default_context()

_SSL_OBJECTS: Dict[str, ssl.SSLObject] = {}

_wrap_bio = SSL_CONTEXT.wrap_bio


def patched_wrap_bio(incoming: ssl.MemoryBIO, outgoing: ssl.MemoryBIO, server_hostname: str, **kwargs) -> ssl.SSLObject:
    global _SSL_OBJECTS  # pylint: disable=global-statement
    ssl_object = _wrap_bio(incoming, outgoing, server_hostname=server_hostname, **kwargs)
    _SSL_OBJECTS[server_hostname] = ssl_object
    return ssl_object


# we monkey patch SSL_CONTEXT to store SSLObjects in _ssl_objects
# (subclassing ssl.SSLContext for some reason didn't work reliably)
SSL_CONTEXT.wrap_bio = patched_wrap_bio


def get_ssl_info(hostname):
    global _SSL_OBJECTS  # pylint: disable=global-statement
    ssl_object = _SSL_OBJECTS.get(hostname)
    if ssl_object:
        cert_dict = ssl_object.getpeercert(binary_form=False)
        cert_bin = ssl_object.getpeercert(binary_form=True)
        # make cert_obj using cert_dict and cert_bin
        cert_obj = cert_to_obj(cert_dict)
        if cert_bin is not None and 'sha256' not in cert_obj:
            update_obj_with_bin(cert_obj, cert_bin)
        return {
            'version': ssl_object.version(),
            'certificate': cert_obj
        }
    else:
        return {}
