import hashlib


def _h(content):
    return hashlib.sha256(content).hexdigest()


DYNAMIC_HASHES = {
    # /translations.js
    _h(b"var could_not_load = 'could not load data!';")
}
