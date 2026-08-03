import hashlib
import ssl
from typing import Dict


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
    for field in ['serialNumber', 'notBefore', 'notAfter']:
        if field in cert:
            obj[field] = cert.get(field)
    if 'subjectAltName' in cert:
        obj.setdefault('subject', {})['altName'] = ', '.join(
            f'{kind}:{value}' for kind, value in cert['subjectAltName'])
    return obj


def update_obj_with_bin(cert_obj, cert_bin):
    subject = cert_obj.get('subject') or {}
    issuer = cert_obj.get('issuer') or {}
    cert_obj['sha256'] = ':'.join(f'{b:02X}' for b in hashlib.sha256(cert_bin).digest())
    cert_obj['subject'] = {
        'commonName': subject.get('commonName'),
        'countryName': subject.get('countryName'),
        'organizationName': subject.get('organizationName'),
    }
    cert_obj['issuer'] = {
        'commonName': issuer.get('commonName'),
        'countryName': issuer.get('countryName'),
        'organizationName': issuer.get('organizationName'),
    }
    if 'altName' in subject:
        cert_obj['subject']['altName'] = subject['altName']


SSL_CONTEXT = ssl.create_default_context()

_SSL_OBJECTS: Dict[str, ssl.SSLObject] = {}

_wrap_bio = SSL_CONTEXT.wrap_bio


def patched_wrap_bio(incoming: ssl.MemoryBIO, outgoing: ssl.MemoryBIO, server_hostname: str, **kwargs) -> ssl.SSLObject:
    global _SSL_OBJECTS  # pylint: disable=global-statement
    ssl_object = _wrap_bio(incoming, outgoing, server_hostname=server_hostname, **kwargs)
    _SSL_OBJECTS[server_hostname.decode()] = ssl_object
    return ssl_object


SSL_CONTEXT.wrap_bio = patched_wrap_bio


def get_ssl_info(hostname):
    global _SSL_OBJECTS  # pylint: disable=global-statement
    ssl_object = _SSL_OBJECTS.get(hostname)
    if ssl_object:
        cert_dict = ssl_object.getpeercert(binary_form=False)
        cert_bin = ssl_object.getpeercert(binary_form=True)
        cert_obj = cert_to_obj(cert_dict)
        if cert_bin is not None and 'sha256' not in cert_obj:
            update_obj_with_bin(cert_obj, cert_bin)
        return {
            'version': ssl_object.version(),
            'certificate': cert_obj,
        }
    return {}
