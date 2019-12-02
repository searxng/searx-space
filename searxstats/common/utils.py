import inspect
import asyncio
import functools


ERROR_REMOVE_PREFIX = "[SSL: CERTIFICATE_VERIFY_FAILED] "


def exception_to_str(ex):
    result = str(ex)
    if result == '':
        result = type(ex).__name__
    elif result.startswith(ERROR_REMOVE_PREFIX):
        result = result[len(ERROR_REMOVE_PREFIX):]
    return result


def dict_update(dictionary: dict, keys: list, value):
    for k in keys[:-1]:
        dictionary = dictionary.setdefault(k, dict())
    if isinstance(value, dict):
        dictionary = dictionary.setdefault(keys[-1], dict())
        dictionary.update(value)
    else:
        dictionary[keys[-1]] = value


# pylint: disable=invalid-name
def dict_merge(a, b, path=None):
    "merges b into a"
    if path is None:
        path = []

    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                dict_merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                raise Exception('Conflict at %s' % '.'.join(path + [str(key)]))
        else:
            a[key] = b[key]
    return a


async def wait_get_results(*tasks):
    """
    Safe
    ```python
    set(map(lambda t: t.result(), await asyncio.wait({*tasks})))

    Raise the first exception.

    t.result() is called for all tasks
    ```
    """
    # check if there is a least one task
    if len(tasks) == 0:
        return set()
    else:
        # run everything in parallel
        try:
            done, pending = await asyncio.wait({*tasks}, return_when=asyncio.ALL_COMPLETED)
        except Exception as ex:
            raise ex
        else:
            assert len(pending) == 0
            assert len(done) == len(tasks)

            # return results
            results = []
            exception = None
            for task in tasks:
                try:
                    results.append(task.result())
                except Exception as ex:
                    # make sure to call task.result() for all tasks
                    # so no break here
                    exception = ex
        if exception is not None:
            raise exception
        return results


def create_task(loop, executor, function, *args, **kwargs):
    if inspect.iscoroutinefunction(function):
        # async task in the loop
        return loop.create_task(function(*args, **kwargs))
    else:
        # run sync tasks in a thread pool
        if kwargs is None or len(kwargs) == 0:
            return loop.run_in_executor(executor, function, *args)
        else:
            # loop.run_in_executor doesn't support keywords arguments
            def wrapped():
                return function(*args, **kwargs)
            functools.update_wrapper(wrapped, function)
            return loop.run_in_executor(executor, wrapped)
