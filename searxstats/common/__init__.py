from .http import initialize as http_initialize


async def initialize():
    await http_initialize()
