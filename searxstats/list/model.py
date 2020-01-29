from collections import OrderedDict
import rfc3986
import yaml
import json
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

# Model

class AdditionalUrlList(OrderedDict, yaml.YAMLObject):

    yaml_tag = '!AdditionalUrlList'
    __slots__ = [ ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return dict(self.items()).__repr__()

    @staticmethod
    def yaml_representer(dumper: yaml.Dumper, additional_url):
        return dumper.represent_dict(additional_url)

    @staticmethod
    def yaml_constructor(loader, node):
        mapping = loader.construct_mapping(node)
        return AdditionalUrlList(**mapping)


class Instance(yaml.YAMLObject):

    yaml_tag = '!Instance'
    __slots__ = ['safe', 'comments', 'additional_urls']

    def __init__(self, safe=False, comments=[], additional_urls=AdditionalUrlList()):
        # type check
        if not isinstance(safe, bool):
            raise ValueError('safe is not a bool')
        if not isinstance(comments, list):
            raise ValueError('comments is not a list')
        if not isinstance(additional_urls, AdditionalUrlList):
            raise ValueError('additional_urls is not a AdditionalUrlList instance')
        # assign
        self.safe = safe
        self.comments = comments
        self.additional_urls = additional_urls

    def to_json(self):
        return dict([
            ("safe", self.safe),
            ("comments", self.comments),
            ("additional_urls", self.additional_urls)
        ])

    def __repr__(self):
        return str(self.to_json())

    @staticmethod
    def yaml_representer(dumper: yaml.Dumper, instance):
        output = [('safe', instance.safe)]
        if instance.comments is not None and len(instance.comments) > 0:
            output.append(('comments', instance.comments))
        if instance.additional_urls is not None and len(instance.additional_urls) > 0:
            output.append(('additional_urls', instance.additional_urls))
        return dumper.represent_dict(output)

    @staticmethod
    def yaml_constructor(loader, node: yaml.MappingNode):
        mapping = loader.construct_mapping(node)
        return Instance(**mapping)


class InstanceList(OrderedDict, yaml.YAMLObject):

    yaml_tag = '!InstanceList'
    __slots__ = [ ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._urls = set()

    def __setitem__(self, url: str, instance: Instance):
        # type check
        if not isinstance(url, str):
            raise ValueError('url is not a str but is ' + str(url))
        if not isinstance(instance, Instance):
            raise ValueError('instance is not a Instance but is ' + str(instance))
        # check for duplicate URL
        new_urls = set([url, *instance.additional_urls.keys()])
        conflict_urls = new_urls.intersection(self.urls)
        if len(conflict_urls) > 0:
            raise ValueError(f'{", ".join(conflict_urls)} already declared')
        # check for URL not normalized
        for url in new_urls:
            nurl = str(rfc3986.normalize_uri(url))
            if nurl != url:
                raise ValueError(f'{url} should be normalized to {nurl}')
        # update
        super().__setitem__(url, instance)

    @property
    def urls(self):
        all_urls = set()
        for url, instance in self.items():
            all_urls.update(set([url, *instance.additional_urls.keys()]))
        return all_urls

    def json_dump(self):
        return json.dumps(self, cls=ObjectEncoder, indent=2, sort_keys=True)

    def __repr__(self):
        s = '{\n'
        for url, instance in self.items():
            s += ' ' + url + ': ' + str(instance) + '\n'
        s += '}'
        return s

    @staticmethod
    def yaml_representer(dumper: yaml.Dumper, instance_list):
        return dumper.represent_dict(instance_list)

    @staticmethod
    def yaml_constructor(loader: yaml.Loader, node):
        mapping = loader.construct_mapping(node)
        return InstanceList(mapping)

# JSON serialization

class ObjectEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return self.default(obj.to_json())
        elif hasattr(obj, "__dict__"):
            d = dict(
                (key, value)
                for key, value in inspect.getmembers(obj)
                if not key.startswith("__")
                and not inspect.isabstract(value)
                and not inspect.isbuiltin(value)
                and not inspect.isfunction(value)
                and not inspect.isgenerator(value)
                and not inspect.isgeneratorfunction(value)
                and not inspect.ismethod(value)
                and not inspect.ismethoddescriptor(value)
                and not inspect.isroutine(value)
            )
            return self.default(d)
        return obj

# YAML (de)serialization

class ILLoader(Loader):
    pass

class ILDumper(Dumper):
    def ignore_aliases(*args):
        return True

for c in [InstanceList, Instance, AdditionalUrlList]:
    ILDumper.add_representer(c, c.yaml_representer)
    ILLoader.add_constructor(c.yaml_tag, c.yaml_constructor)

ILLoader.add_path_resolver('!InstanceList', [ ], yaml.MappingNode)
ILLoader.add_path_resolver('!Instance', [ (yaml.MappingNode, False) ])
ILLoader.add_path_resolver('!AdditionalUrlList', [ None, 'additional_urls' ], yaml.MappingNode)

# Storage

def load(filename) -> InstanceList:
    with open(filename, 'r') as input_file:
        instance_list = yaml.load(input_file, Loader=ILLoader)
        assert isinstance(instance_list, InstanceList)
        return instance_list

def save(filename: str, instance_list: InstanceList):
    output_content = yaml.dump(instance_list, Dumper=ILDumper, width=240, allow_unicode=True)
    with open(filename, 'w') as output_file:
        output_file.write(output_content)


__all__ = [ 'InstanceList', 'Instance', 'AdditionalUrl', 'load', 'save' ]
