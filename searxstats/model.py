import calendar
import datetime
import json

from searxstats.memoize import erase_by_name
from searxstats.utils import create_task


class SearxStatisticsResult:

    __slots__ = 'timestamp', 'instances', 'hashes'

    def __init__(self):
        self.timestamp = calendar.timegm(datetime.datetime.now().utctimetuple())
        self.instances = {}
        self.hashes = []

    @staticmethod
    def _is_valid_instance(detail):
        return detail.get('version', None) is not None and 'error' not in detail

    def iter_valid_instances(self):
        for instance, detail in self.instances.items():
            if self._is_valid_instance(detail):
                yield instance, detail

    def iter_all_instances(self):
        for instance, detail in self.instances.items():
            yield instance, detail

    def get_instance(self, url):
        return self.instances[url]

    def create_instance(self, url, detail):
        self.instances[url] = detail

    def update_instance(self, url, detail):
        if url in self.instances:
            self.instances[url].update(detail)
        else:
            self.instances[url] = detail

    def write(self, output_file_name):
        searx_json = {
            'timestamp': self.timestamp,
            'instances': self.instances,
            'hashes': self.hashes
        }
        with open(output_file_name, "w") as output_file:
            json.dump(searx_json, output_file, indent=4, ensure_ascii=False)


class Fetcher:

    __slots__ = 'name', 'help_message', 'fetch_function'

    def __init__(self, name, help_message, fetch_function):
        self.name = name
        self.help_message = help_message
        self.fetch_function = fetch_function

    def create_task(self, loop, searx_stats_result: SearxStatisticsResult):
        return create_task(loop, self.fetch_function, searx_stats_result)

    @property
    def memoize_key_prefix(self):
        return str(self.fetch_function.__module__)

    def erase_memoize(self):
        erase_by_name(str(self.memoize_key_prefix))
