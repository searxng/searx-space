from .http import initialize as http_initialize
from .queuecalls import finalize as queuecalls_finalize


async def initialize():
    await http_initialize()


async def finalize():
    await queuecalls_finalize()
