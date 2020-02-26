import statistics


def parse_server_timings(server_timing):
    """
    Parse the Server-Timing header
    See
    - https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Server-Timing
    - https://w3c.github.io/server-timing/#the-server-timing-header-field
    """
    if server_timing == '':
        return dict()

    def parse_param(param):
        """
        Parse `dur=2067.665` or `desc="Total time"`

        Convert `dur` param to second from millisecond
        """
        param = tuple(param.strip().split('='))
        if param[0] == 'dur':
            return param[0], float(param[1]) / 1000
        else:
            return param[0], param[1]

    def parse_metric(str_metric):
        """
        Parse
        - `total;dur=2067.665;desc="Total time"`
        - or `total_0_ddg;dur=512.808` etc..
        """
        str_metric = str_metric.strip().split(';')
        name = str_metric[0].strip()
        param_tuples = map(parse_param, str_metric[1:])
        params = dict(param_tuples)
        return name, params

    raw_timing_list = server_timing.split(',')
    timing_list = list(map(parse_metric, raw_timing_list))
    return dict(timing_list)


def timings_stats(timings):
    if len(timings) >= 2:
        return {
            'median': round(statistics.median(timings), 3),
            'stdev': round(statistics.stdev(timings), 3),
            'mean': round(statistics.mean(timings), 3)
        }
    elif len(timings) == 1:
        return {
            'value': round(timings[0], 3)
        }
    else:
        return None


def get_load_time(one_server_timings):
    load_timings = dict(filter(lambda i: i[0].startswith('load_'), one_server_timings.items()))
    load_timings = list(map(lambda v: v.get('dur', None), load_timings.values()))
    if len(load_timings) > 0:
        return max(load_timings)
    else:
        return None


def set_timings_stats(result, key, timings):
    stats = timings_stats(timings)
    if stats is not None:
        result[key] = stats


class ResponseTimeStats:

    def __init__(self):
        self.all_timings = []
        self.server_timings = []
        self.load_timings = []
        self.count = 0

    def add_response(self, response):
        self.count += 1
        if response is not None:
            self.all_timings.append(response.elapsed.total_seconds())
            server_timing_values = parse_server_timings(response.headers.get('server-timing', ''))
            server_time = server_timing_values.get('total', {}).get('dur', None)
            if server_time is not None:
                self.server_timings.append(server_time)
            load_time = get_load_time(server_timing_values)
            if load_time is not None:
                self.load_timings.append(load_time)

    def get(self):
        if self.count == 0:
            result = {}
        else:
            result = {
                'success_percentage': round(len(self.all_timings) * 100 / self.count, 0)
            }
            set_timings_stats(result, 'all', self.all_timings)
            set_timings_stats(result, 'server', self.server_timings)
            set_timings_stats(result, 'load', self.load_timings)
        return result
