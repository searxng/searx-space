import asyncio
import inspect
import functools


class CallQueue:

    __ALL_INSTANCES__ = {}

    __slots__ = 'queue', 'workers', 'loop'

    def __init__(self, name, worker_count=1, loop=None):
        if name in CallQueue.__ALL_INSTANCES__:
            raise ValueError(f'{name} CallQueue already exists')

        if loop is None:
            loop = asyncio.get_event_loop()

        self.loop = loop
        self.queue = asyncio.Queue()

        self.workers = []
        for _ in range(worker_count):
            task = loop.create_task(self._worker())
            self.workers.append(task)

        CallQueue.__ALL_INSTANCES__[name] = self

    async def close(self):
        for _ in self.workers:
            await self.queue.put((None, None))
        for task in self.workers:
            task.cancel()

    @staticmethod
    def get(name):
        return CallQueue.__ALL_INSTANCES__[name]

    @staticmethod
    async def close_all():
        for call_queue in CallQueue.__ALL_INSTANCES__.values():
            await call_queue.close()

    async def _worker(self):
        while True:
            future, coroutine = await self.queue.get()
            if future is None:
                self.queue.task_done()
                return
            try:
                result = await coroutine
            except Exception as ex:
                future.set_exception(ex)
            else:
                future.set_result(result)
            finally:
                self.queue.task_done()

    async def __call__(self, coroutine):
        future = self.loop.create_future()
        await self.queue.put((future, coroutine))
        return await future


class UseQueue:

    __slots__ = ['call_queue']

    def __init__(self, worker_count=None, name=None, loop=None):
        if name is not None:
            call_queue = CallQueue.get(name)
        elif worker_count is not None:
            queue_name = id(self)
            call_queue = CallQueue(queue_name, worker_count=worker_count, loop=loop)
        else:
            raise RuntimeError('Either count or call_queue_name must be set')

        self.call_queue = call_queue

    def __call__(self, function):
        async def wrapped(*args, **kwargs):
            coroutine = function(*args, **kwargs)
            return await self.call_queue(coroutine)

        if not inspect.iscoroutinefunction(function):
            raise ValueError('function as to be a coroutine')

        functools.update_wrapper(wrapped, function)
        return wrapped


async def finalize():
    await CallQueue.close_all()
