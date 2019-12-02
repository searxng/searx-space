from .ssl_utils import monkey_patch as ssl_utils_monkey_patch
from .http import initialize as http_initialize
from .queuecalls import finalize as queuecalls_finalize


async def initialize():
    ssl_utils_monkey_patch()
    await http_initialize()


async def finalize():
    await queuecalls_finalize()
