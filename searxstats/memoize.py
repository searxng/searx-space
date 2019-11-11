import time
import atexit
import inspect
import copy
import os.path
import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


class NotCachedValueClass():
    pass


NOT_CACHED_VALUE = NotCachedValueClass()


class CacheStorage:

    def __init__(self, *args, **kwargs):
        pass

    # # pylint: disable=no-self-use
    def get(self, args):
        raise ValueError('Not Implemented')

    # # pylint: disable=no-self-use
    def put(self, args, value):
        raise ValueError('Not Implemented')


class SimpleCacheStorage(CacheStorage):

    def __init__(self):
        super(SimpleCacheStorage, self).__init__()
        self.data = {}

    def get(self, args):
        return self.data.get(args, NOT_CACHED_VALUE)

    def put(self, args, value):
        self.data[args] = value


class ExpireCacheStorage(CacheStorage):

    __slots__ = 'data', 'expire_time'

    def __init__(self, data, expire_time):
        super(ExpireCacheStorage, self).__init__()
        self.data = data
        self.expire_time = expire_time

    def get(self, args):
        raw_data = self.data.get(args, None)
        if raw_data is None:
            return NOT_CACHED_VALUE
        timestamp = raw_data['t']
        value = raw_data['v']
        if self.expire_time is not None and (time.time() - timestamp) > self.expire_time:
            return NOT_CACHED_VALUE
        return copy.deepcopy(value)

    def put(self, args, value):
        self.data[args] = {
            't': time.time(),
            'v': copy.deepcopy(value)
        }


class FileStorageBackend():

    __slots__ = 'file_name', 'storage'

    def __init__(self):
        self.file_name = None
        self.storage = None

    def bind_to_file(self, file_name):
        self.file_name = file_name
        self.storage = self._load_cache()
        atexit.register(self._write_cache)

    def get_cache_storage(self, key, expire_time=None):
        if self.storage is None:
            raise ValueError('FileStorageBackend is not bound to a file')
        if key not in self.storage:
            self.storage[key] = {}
        return ExpireCacheStorage(self.storage[key], expire_time=expire_time)

    def _load_cache(self):
        if self.file_name is not None:
            try:
                if os.path.exists(self.file_name):
                    print('\nLoading cache {}'.format(self.file_name))
                    with open(self.file_name, "r") as input_file:
                        return yaml.load(input_file, Loader=Loader)
                else:
                    return {}
            except Exception as ex:
                print(ex)
                return {}
        else:
            raise ValueError('file_name is not specified')

    def _write_cache(self):
        if self.file_name is not None:
            print('\nSaving cache {}'.format(self.file_name))
            with open(self.file_name, "w") as output_file:
                output_content = yaml.dump(self.storage, Dumper=Dumper)
                output_file.write(output_content)

    def erase_by_name(self, name_start):
        if self.storage is None:
            raise ValueError('FileStorageBackend is not bound to a file')
        for key in self.storage:
            if key.startswith(name_start):
                self.storage[key] = {}


class BaseMemoize:

    __slots__ = 'func_key', 'validate_result', '_func', '_storage'

    def __init__(self, storage, func_key=None, validate_result=None):
        self.func_key = func_key
        self.validate_result = validate_result
        self._func = None
        self._storage = storage

    @property
    def storage(self):
        return self._storage

    @property
    def func(self):
        return self._func

    def __call__(self, func):
        self._func = func

        def func_key_simple(*args, **kwargs):
            if len(kwargs.values()) > 0:
                raise ValueError('@Memoize doesn\' support keyword arguments')
            return args

        # pylint: disable=unused-argument
        def validate_result_true(result):
            return True

        func_key = self.func_key if self.func_key is not None else func_key_simple
        validate_result_func = self.validate_result if self.validate_result is not None else validate_result_true

        # function
        def wrapped_f(*args, **kwargs):
            storage = self.storage
            cached_key = func_key(*args, **kwargs)
            cached_value = storage.get(cached_key)
            if cached_value != NOT_CACHED_VALUE:
                # use cache value
                return cached_value
            # empty cache or expired value
            result = func(*args, **kwargs)
            if validate_result_func(result):
                storage.put(cached_key, result)
            return result

        # coroutine
        async def wrapped_async_f(*args, **kwargs):
            storage = self.storage
            cached_key = func_key(*args, **kwargs)
            cached_value = storage.get(cached_key)
            if cached_value != NOT_CACHED_VALUE:
                # use cache value
                return cached_value
            # empty cache or expired value
            result = await func(*args, **kwargs)
            if validate_result_func(result):
                storage.put(cached_key, result)
            return result

        if inspect.iscoroutinefunction(func):
            wrapped = wrapped_async_f
        else:
            wrapped = wrapped_f

        wrapped.no_memoize = func
        wrapped.__name__ = func.__name__
        wrapped.__doc__ = func.__doc__
        return wrapped


DEFAULT_STORAGE_BACKEND = FileStorageBackend()


def bind_to_file_name(file_name):
    DEFAULT_STORAGE_BACKEND.bind_to_file(file_name)


def erase_by_name(name_start):
    DEFAULT_STORAGE_BACKEND.erase_by_name(name_start)


class MemoizeToDisk(BaseMemoize):

    __slots__ = 'storage_backend', 'expire_time'

    def __init__(self, func_key=None, validate_result=None,
                 storage_backend=DEFAULT_STORAGE_BACKEND, expire_time=24*3600):
        super().__init__(None, func_key=func_key, validate_result=validate_result)
        self.storage_backend = storage_backend
        self.expire_time = expire_time

    @property
    def storage(self):
        if self._storage is None:
            # Perhaps add ','.join(list(inspect.signature(f).parameters.keys()))
            storage_key = self._func.__module__ + '.' + self._func.__name__
            self._storage = self.storage_backend.get_cache_storage(storage_key, expire_time=self.expire_time)
        return self._storage


class Memoize(BaseMemoize):

    def __init__(self, func_key=None, validate_result=None):
        super().__init__(SimpleCacheStorage(), func_key=func_key, validate_result=validate_result)
