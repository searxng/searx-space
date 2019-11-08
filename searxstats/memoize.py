import time
import atexit
import pickle
import inspect

class CacheStorage:

    def __init__(self):
        self.data = {}

    def load(self, _, args):
        return self.data.get(args, None)

    def save(self, _, args, value):
        self.data[args] = value


class FileCacheStorage(CacheStorage):

    def __init__(self, file_name=None, expire_time=None):
        super(FileCacheStorage, self).__init__()
        self.file_name = file_name
        self.expire_time = expire_time
        self.data = {}
        self.load_cache()
        atexit.register(self.write_cache)

    def _load_for_key(self, key):
        if key not in self.data:
            self.data[key] = {}
        return self.data[key]

    def load(self, key, args):
        data_for_key = self._load_for_key(key)
        if args not in data_for_key:
            return None
        raw_data = data_for_key[args]
        timestamp = raw_data['t']
        value = raw_data['v']
        if self.expire_time is not None and (time.time() - timestamp) > self.expire_time:
            return None
        return value

    def save(self, key, args, value):
        data_for_key = self._load_for_key(key)
        data_for_key[args] = {
            't': time.time(),
            'v': value
        }

    def load_cache(self):
        if self.file_name is not None:
            try:
                with open(self.file_name, "rb") as input_file:
                    unpickle_for_data = pickle.Unpickler(input_file, fix_imports=False)
                    self.data = unpickle_for_data.load()
            except Exception as ex:
                print(ex)

    def write_cache(self):
        if self.file_name is not None:
            print('\nSaving cache {}'.format(self.file_name))
            with open(self.file_name, "wb") as output_file:
                pickle_for_data = pickle.Pickler(output_file, protocol=4, fix_imports=False)
                pickle_for_data.dump(self.data)


class Memoize:

    __slots__ = 'storage',

    def __init__(self, storage):
        self.storage = storage or CacheStorage()

    def __call__(self, func):
        # FIXME ? add func.__defaults__ / func.__kwdefaults__
        storage_key = func.__module__ + '.' + func.__name__

        def wrapped_f(*args):
            cached_value = self.storage.load(storage_key, args)
            if cached_value is not None:
                # use cache value
                return cached_value
            # empty cache or expired value
            new_value = func(*args)
            self.storage.save(storage_key, args, new_value)
            return new_value

        async def wrapped_async_f(*args):
            cached_value = self.storage.load(storage_key, args)
            if cached_value is not None:
                # use cache value
                return cached_value
            # empty cache or expired value
            new_value = await func(*args)
            self.storage.save(storage_key, args, new_value)
            return new_value

        if inspect.iscoroutinefunction(func):
            wrapped = wrapped_async_f
        else:
            wrapped = wrapped_f

        wrapped.no_memoize = func
        wrapped.__name__ = func.__name__
        wrapped.__doc__ = func.__doc__
        return wrapped


DEFAULT_STORAGE = FileCacheStorage(file_name='/tmp/searxstats.cache', expire_time=3600*24)


class MemoizeToDisk(Memoize):

    def __init__(self):
        super().__init__(DEFAULT_STORAGE)
