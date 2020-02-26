import jinja2


def http_status_to_class(http_status: str) -> str:
    if http_status is not None:
        http_status = int(http_status)
        if 300 > http_status >= 200:
            return 'label-success'
        elif 400 > http_status >= 300:
            return 'label-warning'
        elif 500 > http_status >= 400:
            return 'label-danger'
        elif http_status >= 500:
            return 'label-danger'
    return None


def set_environment(environment: jinja2.Environment):
    environment.filters['http_status_to_class'] = http_status_to_class


