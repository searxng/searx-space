import inspect
import asyncio

from .utils import create_task


async def _for_each_coroutine(iterator, function, *args):
    for item in iterator:
        await function(*args, *item)


def _for_each_in_thread(iterator, function, *args):
    for item in iterator:
        function(*args, *item)


# pylint: disable=too-many-locals
async def _for_each_parallel(iterator, function, *args,
                             loop=None,
                             executor=None,
                             limit=None):
    assert limit != 1
    semaphore = asyncio.Semaphore(limit) if limit is not None and limit > 0 else None
    errors = set()
    waiter = loop.create_future()
    task_done_target = 0
    task_done_counter = 0
    task_seen_counter = 0
    current_tasks = set()

    def on_task_done(task):
        nonlocal task_done_counter, task_done_target, waiter, current_tasks, semaphore
        if semaphore is not None:
            semaphore.release()
        current_tasks.remove(task)
        task_done_counter += 1
        if task_done_target != 0 and task_done_counter >= task_done_target:
            waiter.set_result(True)

        assert (task_done_target == 0) or (task_done_counter <= task_done_target)

        if task.cancelled():
            return

        exc = task.exception()
        if exc is None:
            return

        errors.add(exc)
        waiter.set_result(False)

    for item in iterator:
        if semaphore is not None:
            await semaphore.acquire()
        task = create_task(loop, executor, function, *args, *item)
        task.add_done_callback(on_task_done)
        task_seen_counter += 1
        current_tasks.add(task)

    if task_done_counter < task_seen_counter:
        task_done_target = task_seen_counter
        try:
            await waiter
        finally:
            for task in current_tasks:
                task.remove_done_callback(on_task_done)
                task.cancel()

    if len(errors) == 1:
        raise errors.pop()

    if len(errors) > 1:
        # FIXME
        raise errors.pop()


def _create_list_iterator(iterator):
    """
    helper to be able to call function(*item) later
    """
    for item in iterator:
        if isinstance(item, (list, tuple)):
            yield item
        else:
            yield [item]


async def for_each(iterator, function, *args,
                   loop=None,
                   executor=None,
                   limit=1):
    """
    If `function` is a coroutine and `limit`is 1, equivalent of
    ```
    for item in iterator:
        await function(*args, *item)
    ```
    Raise the first encountered exception.

    No return value.

    `function` doesn't have to be  be a coroutine:
    - If it is a coroutine, `loop` will be used (or the default one).
    - Otherwise, `executor` (or the default one) will be used to run the function in a separated thread.

    About `limit`:
    - The default value is 1: calls to `function` are sequentials.
    - When `limit` is 0, all the calls to `function` are run concurently.
    - When `limit` is more than 1, limit the number of calls to `function` to the `limit` value.

    When `limit` is different from 1, and `function` raises an exception multiple times,
    `for_each` may not raise the first exception.

    External links to other implementations:
    - https://paco.readthedocs.io/en/latest/api.html#paco.each :
      no support for executor
    - https://github.com/edgedb/edgedb/blob/master/edb/common/taskgroup.py :
      special care of cancelled tasks, but no `limit` support
    - https://bugs.python.org/issue30782 :
      Allow limiting the number of concurrent tasks in asyncio.as_completed
    """
    if loop is None:
        loop = asyncio.get_event_loop()

    iterator = _create_list_iterator(iterator)

    if limit == 1:
        if inspect.iscoroutinefunction(function):
            await _for_each_coroutine(iterator, function, *args)
        else:
            await loop.run_in_executor(executor, _for_each_in_thread, iterator, function, *args)
    else:
        await _for_each_parallel(iterator, function, *args,
                                 loop=loop,
                                 executor=executor,
                                 limit=limit)
